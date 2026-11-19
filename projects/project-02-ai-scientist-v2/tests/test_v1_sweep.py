"""Flexible matrix and frozen-artifact checks, without downloads or real attacks."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from course_tools import run_v1_sweep as sweep


class SweepProtocolTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((sweep.ROOT / "configs/v1_crossover.json").read_text(encoding="utf-8"))

    def read_changed(self, **changes):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({**self.config, **changes}), encoding="utf-8")
            return sweep.read_config(path)

    def test_plan_uses_exact_equal_budgets_and_actual_seed_jobs(self):
        config = self.read_changed()
        plan = sweep.make_plan(config)
        self.assertEqual(plan["generation_jobs"], 20)
        self.assertEqual(plan["mi_generation_jobs"], 5)
        self.assertEqual(plan["bsr_generation_jobs"], 15)
        self.assertEqual(plan["total_sample_view_gradient_evaluations"], 600000)
        self.assertEqual(plan["comparisons_per_target_subset"], 5)
        self.assertEqual(len(plan["methods"]), 10)
        self.assertEqual(len({job["job_id"] for job in plan["jobs"]}), 20)
        for method in plan["methods"]:
            self.assertEqual(method["steps"] * method["views"], method["gradient_budget"])
            if method["method"] == "bsr":
                self.assertEqual(method["seeds"], [42, 142, 242])
                self.assertAlmostEqual(method["steps"] * method["alpha"], config["epsilon"])
            else:
                self.assertEqual(method["seeds"], [None])
                self.assertAlmostEqual(method["alpha"], config["epsilon"] / 10)

    def test_nondivisible_or_duplicate_budgets_are_rejected_before_execution(self):
        for changes, message in (({"gradient_budgets": [25, 30, 35]}, "divisible"),
                                 ({"gradient_budgets": [30], "views": [1, 2, 4]}, "divisible"),
                                 ({"gradient_budgets": [20, 20]}, "Duplicate"),
                                 ({"gradient_budgets": [True]}, "positive integer"),
                                 ({"views": [2]}, "MI view 1")):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                self.read_changed(**changes)

    def test_seed_counts_can_change_but_batch_streams_must_not_overlap(self):
        for seeds in ([42], [42, 142, 242, 342, 442]):
            config = self.read_changed(bsr_seeds=seeds)
            plan = sweep.make_plan(config)
            self.assertEqual(plan["bsr_generation_jobs"], 5 * len(seeds))
            self.assertEqual(plan["mi_generation_jobs"], 5)
            self.assertEqual(plan["total_sample_view_gradient_evaluations"], 150000 * (1 + len(seeds)))
        # 1000/20 = 50 batches, so a base difference of 49 reuses a seed.
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.read_changed(bsr_seeds=[42, 91])
        self.read_changed(bsr_seeds=[42, 92])
        # Shrinking the batch size increases seed-stream length.
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.read_changed(batch_size=5)

    def test_step_rules_and_denominator_have_their_actual_meaning(self):
        config = self.read_changed(mi_step_rules=["fixed", "epsilon_over_steps"], fixed_step_denominator=5)
        methods = {method["name"]: method for method in sweep.build_methods(config)}
        self.assertAlmostEqual(methods["mi_g30_fixed_step"]["alpha"], config["epsilon"] / 5)
        self.assertEqual(methods["mi_g30_fixed_step"]["alpha_kind"], "fixed_epsilon_over_denominator")
        self.assertAlmostEqual(methods["mi_g30"]["alpha"], config["epsilon"] / 30)
        self.assertEqual(set(sweep.comparison_pairs(list(methods.values()), 30)),
                         {("bsr_m2_g30", "mi_g30"), ("bsr_m2_g30", "mi_g30_fixed_step")})

    def test_supported_targets_are_dynamic_but_selection_stays_fixed(self):
        self.read_changed(target_models=["cifar10_mobilenetv2_x1_0", "cifar10_vgg11_bn"])
        for changes, expected in (({"target_models": ["cifar10_resnet20"]}, "Source must"),
                                  ({"target_models": ["unknown"]}, "registry"),
                                  ({"target_models": []}, "one or two"),
                                  ({"sample_count": 100}, "exactly 1000")):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, expected):
                self.read_changed(**changes)

    def test_plan_does_not_initialize_gpu_assets_or_output(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "must-not-exist"
            with patch.object(sweep.pilot, "setup_runtime", side_effect=AssertionError("GPU initialized")), \
                 patch.object(sweep, "prepare_assets", side_effect=AssertionError("Assets initialized")), \
                 patch.object(sweep, "prepare_run", side_effect=AssertionError("Output initialized")), \
                 redirect_stdout(output):
                sweep.main(["--plan", "--output", str(out)])
            self.assertFalse(out.exists())
        self.assertEqual(json.loads(output.getvalue())["total_sample_view_gradient_evaluations"], 600000)

    def test_resume_freezes_settings_selection_code_assets_and_sweep_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = root / "code.py"
            code.write_text("original", encoding="utf-8")
            out = root / "run"
            assets = {key: {} for key in ("model_repository", "model_commit", "sources", "models", "dataset")}
            kwargs = {"source_root": root, "source_files": ("code.py",), "env": {}}
            original = sweep.prepare_run(out, self.config, {"ids": [1]}, assets, **kwargs)
            self.assertEqual(original["stage"], "exploratory_sweep")
            self.assertIn("not a fresh held-out", original["target_access"])
            resumed = sweep.prepare_run(out, self.config, {"ids": [1]}, assets, resume=True, **kwargs)
            self.assertEqual(original["frozen_at"], resumed["frozen_at"])
            with self.assertRaisesRegex(ValueError, "config or selection"):
                sweep.prepare_run(out, {**self.config, "bsr_seeds": [42]}, {"ids": [1]}, assets, resume=True, **kwargs)
            with self.assertRaisesRegex(ValueError, "config or selection"):
                sweep.prepare_run(out, self.config, {"ids": [2]}, assets, resume=True, **kwargs)
            with self.assertRaisesRegex(ValueError, "assets differ"):
                sweep.prepare_run(out, self.config, {"ids": [1]}, {**assets, "models": {"different": True}}, resume=True, **kwargs)
            code.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "code differs"):
                sweep.prepare_run(out, self.config, {"ids": [1]}, assets, resume=True, **kwargs)
            code.write_text("original", encoding="utf-8")
            provenance = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
            provenance["stage"] = "full"
            (out / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not this exploratory"):
                sweep.prepare_run(out, self.config, {"ids": [1]}, assets, resume=True, **kwargs)


class SweepPipelineTests(unittest.TestCase):
    def test_source_only_generation_precedes_targets_and_completed_resume_verifies_caches(self):
        config = json.loads((sweep.ROOT / "configs/v1_crossover.json").read_text(encoding="utf-8"))
        config.update(gradient_budgets=[20, 30], bsr_seeds=[42, 142, 242, 342, 442],
                      target_models=["cifar10_mobilenetv2_x1_0", "cifar10_vgg11_bn"], bootstrap_replicates=10)
        labels = torch.arange(10)
        images = torch.zeros((10, 3, 2, 2))
        images[:, 0, 0, 0] = labels / 10
        selection = {"final_ids": list(range(10)), "pilot_ids": [0, 1], "development_ids": list(range(10)),
                     "subsets": {"full1000": list(range(10)), "pilot200": [0, 1], "new800": list(range(2, 10))}}
        generated, loaded_targets = [], []

        def load(name, *args):
            if name != config["source_model"]:
                self.assertEqual(len(generated), 12)
                loaded_targets.append(name)
            return SimpleNamespace(name=name)

        def generate(model, x, y, attack, settings, device, progress):
            self.assertEqual(model.name, config["source_model"])
            generated.append((attack.name, settings["attack_seed"]))
            return x.clone(), {"sample_view_gradient_evaluations": len(x) * attack.steps * attack.views,
                               "gradient_evaluations_per_image": attack.steps * attack.views,
                               "attack_seconds": 1.0, "peak_cuda_allocated_mib": 1.0}

        def predict(model, x, *args):
            return torch.round(x[:, 0, 0, 0] * 10).long().numpy()

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "cache").mkdir()
            with patch.object(sweep.pilot, "load_tensors", return_value=(images, labels)), \
                 patch.object(sweep, "load_model", side_effect=load), \
                 patch.object(sweep.pilot, "full_clean_accuracy", return_value={"accuracy": 1.0, "correct": 10, "count": 10}), \
                 patch.object(sweep.pilot, "predict", side_effect=predict), \
                 patch.object(sweep.full, "warmup", return_value={"included_in_attack_budget": False}), \
                 patch.object(sweep.pilot, "run_batched", side_effect=generate), \
                 patch.object(sweep.torch.cuda, "empty_cache"), redirect_stdout(io.StringIO()):
                result = sweep.run_experiment(out, config, selection, None, None, "cpu")
                sweep.verify_completed_run(out, config, selection, None)
                with (out / "summary.csv").open("a", encoding="utf-8") as stream:
                    stream.write("tampered\n")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    sweep.verify_completed_run(out, config, selection, None)
            self.assertEqual(result["stage"], "exploratory_sweep")
            self.assertEqual(loaded_targets, config["target_models"])
            self.assertEqual(len(result["jobs"]), 12)
            self.assertEqual(sum(job["seed"] is None for job in result["jobs"]), 2)
            self.assertEqual(sum(job["seed"] is not None for job in result["jobs"]), 10)
            self.assertEqual(len(result["summary"]), 24)
            self.assertEqual(len(result["comparisons"]), 12)
            self.assertEqual(result["total_sample_view_gradient_evaluations"], 3000)
            bsr_rows = [row for row in result["summary"] if row["method"].startswith("bsr")]
            self.assertTrue(all(row["attack_seed_count"] == 5 for row in bsr_rows))
            self.assertTrue((out / "per_seed.csv").exists())
            self.assertTrue((out / "predictions.csv").exists())


if __name__ == "__main__":
    unittest.main()
