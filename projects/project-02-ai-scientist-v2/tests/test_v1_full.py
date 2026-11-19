"""Scientific protocol and artifact integrity checks without model downloads."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import torch

from course_tools import run_v1_full as full


class FullProtocolTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((full.ROOT / "configs/v1_full.json").read_text(encoding="utf-8"))

    def test_matrix_has_13_methods_25_jobs_and_declared_gradient_cost(self):
        methods = full.build_methods(self.config)
        jobs = full.build_jobs(methods)
        by_name = {method["name"]: method for method in methods}
        self.assertEqual(len(methods), 13)
        self.assertEqual(len(jobs), 25)
        self.assertEqual(len({job["job_id"] for job in jobs}), 25)
        self.assertEqual(sum(by_name[job["method"]]["gradient_budget"] * 1000 for job in jobs), 1130000)
        self.assertEqual(sum(job["seed"] is None for job in jobs), 7)
        self.assertEqual(sum(job["seed"] is not None for job in jobs), 18)
        for budget in (20, 40, 80):
            for name in (f"mi_g{budget}", f"bsr_m2_g{budget}", f"bsr_m4_g{budget}"):
                method = by_name[name]
                self.assertEqual(method["steps"] * method["views"], budget)
                self.assertAlmostEqual(method["steps"] * method["alpha"], self.config["epsilon"])
            self.assertEqual(by_name[f"mi_g{budget}_fixed_step"]["alpha"], self.config["epsilon"] / 10)

    def test_inherited_ids_and_order_are_preserved_and_new_subset_is_disjoint(self):
        inherited = json.loads((full.ROOT / self.config["selection_source"]).read_text(encoding="utf-8"))
        selected = full.selection_from_record(inherited)
        self.assertEqual(selected["final_ids"], inherited["final_ids"])
        self.assertEqual(selected["pilot_ids"], inherited["pilot_ids"])
        self.assertEqual(len(selected["new_ids"]), 800)
        self.assertFalse(set(selected["new_ids"]) & set(selected["pilot_ids"]))
        self.assertEqual(set(selected["new_ids"]) | set(selected["pilot_ids"]), set(selected["final_ids"]))

    def test_duplicate_or_inconsistent_inherited_ids_are_rejected(self):
        inherited = json.loads((full.ROOT / self.config["selection_source"]).read_text(encoding="utf-8"))
        duplicate = {**inherited, "final_ids": inherited["final_ids"][:-1] + inherited["final_ids"][:1]}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            full.selection_from_record(duplicate)
        bad_pilot = {**inherited, "pilot_ids": list(range(200))}
        with self.assertRaisesRegex(ValueError, "subset"):
            full.selection_from_record(bad_pilot)

    def test_nonoverlapping_seed_streams_and_models_are_checked_before_gpu(self):
        for changes, expected in (({"bsr_seeds": [42, 43, 44]}, "overlap"),
                                  ({"target_models": ["cifar10_mobilenetv2_x1_0", "unknown"]}, "registry")):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"
                path.write_text(json.dumps({**self.config, **changes}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, expected):
                    full.read_config(path)


class CacheIntegrityTests(unittest.TestCase):
    def setUp(self):
        config = json.loads((full.ROOT / "configs/v1_full.json").read_text(encoding="utf-8"))
        self.method = full.build_methods(config)[0]
        self.job = full.build_jobs([self.method])[0]
        self.images = torch.full((2, 3, 2, 2), 0.5)
        self.labels = torch.tensor([1, 2])
        self.ids = [100, 200]
        self.payload = {"adversarial": self.images.clone(), "labels": self.labels, "ids": self.ids,
                        "source_predictions": self.labels.clone(), "linf": torch.zeros(2)}
        self.generation = {"gradient_evaluations_per_image": 10, "sample_view_gradient_evaluations": 20}

    def test_completed_cache_roundtrip_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "cache").mkdir()
            full.save_cached_job(out, self.job, self.method, self.payload, self.generation)
            loaded, generation = full.load_cached_job(out, self.job, self.method, self.images, self.labels, self.ids)
            torch.testing.assert_close(loaded["adversarial"], self.images)
            self.assertEqual(generation, self.generation)
            tensor_path, _, _ = full.cache_paths(out, self.job)
            with tensor_path.open("ab") as stream:
                stream.write(b"tampered")
            with self.assertRaisesRegex(ValueError, "checksum"):
                full.load_cached_job(out, self.job, self.method, self.images, self.labels, self.ids)

    def test_incomplete_cache_is_not_trusted_and_changed_job_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "cache").mkdir()
            tensor_path, _, _ = full.cache_paths(out, self.job)
            torch.save(self.payload, tensor_path)
            self.assertIsNone(full.load_cached_job(out, self.job, self.method, self.images, self.labels, self.ids))
            full.save_cached_job(out, self.job, self.method, self.payload, self.generation)
            with self.assertRaisesRegex(ValueError, "specification"):
                full.load_cached_job(out, self.job, {**self.method, "alpha": 0.01}, self.images, self.labels, self.ids)

    def test_cache_with_wrong_ids_or_excessive_perturbation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "labels or IDs"):
            full.validate_payload({**self.payload, "ids": [100, 201]}, self.images, self.labels, self.ids, self.method)
        with self.assertRaisesRegex(ValueError, "epsilon"):
            full.validate_payload({**self.payload, "adversarial": self.images + 0.1}, self.images, self.labels, self.ids, self.method)

    def test_resume_requires_frozen_config_selection_code_and_asset_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "code.py").write_text("original", encoding="utf-8")
            out = root / "run"
            assets = {key: {} for key in ("model_repository", "model_commit", "sources", "models", "dataset")}
            kwargs = {"source_root": root, "source_files": ("code.py",), "env": {}}
            original = full.prepare_run(out, {"a": 1}, {"ids": [1]}, assets, **kwargs)
            resumed = full.prepare_run(out, {"a": 1}, {"ids": [1]}, assets, resume=True, **kwargs)
            self.assertEqual(original["frozen_at"], resumed["frozen_at"])
            with self.assertRaisesRegex(ValueError, "config or selection"):
                full.prepare_run(out, {"a": 2}, {"ids": [1]}, assets, resume=True, **kwargs)
            with self.assertRaisesRegex(ValueError, "assets differ"):
                full.prepare_run(out, {"a": 1}, {"ids": [1]}, {**assets, "models": {"changed": True}}, resume=True, **kwargs)
            (root / "code.py").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "code differs"):
                full.prepare_run(out, {"a": 1}, {"ids": [1]}, assets, resume=True, **kwargs)


class PipelineIsolationTests(unittest.TestCase):
    def test_all_generation_precedes_targets_and_mi_is_not_pseudoreplicated(self):
        config = json.loads((full.ROOT / "configs/v1_full.json").read_text(encoding="utf-8"))
        config["bootstrap_replicates"] = 10
        labels = torch.arange(10)
        images = torch.zeros((10, 3, 2, 2))
        images[:, 0, 0, 0] = labels / 10
        selection = {"final_ids": list(range(10)), "pilot_ids": [0, 1], "development_ids": list(range(10)),
                     "subsets": {"full1000": list(range(10)), "pilot200": [0, 1], "new800": list(range(2, 10))}}
        generated = []
        loaded_targets = []

        def load(name, *args):
            if name != config["source_model"]:
                self.assertEqual(len(generated), 25)
                loaded_targets.append(name)
            return SimpleNamespace(name=name)

        def generate(model, x, y, attack, settings, device, progress):
            self.assertEqual(model.name, config["source_model"])
            generated.append(attack.name)
            return x.clone(), {"sample_view_gradient_evaluations": len(x) * attack.steps * attack.views,
                               "gradient_evaluations_per_image": attack.steps * attack.views,
                               "attack_seconds": 1.0, "peak_cuda_allocated_mib": 1.0}

        def predict(model, x, *args):
            return torch.round(x[:, 0, 0, 0] * 10).long().numpy()

        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "cache").mkdir()
            with patch.object(full.pilot, "load_tensors", return_value=(images, labels)), \
                 patch.object(full, "load_model", side_effect=load), \
                 patch.object(full.pilot, "full_clean_accuracy", return_value={"accuracy": 1.0, "correct": 10, "count": 10}), \
                 patch.object(full.pilot, "predict", side_effect=predict), \
                 patch.object(full, "warmup", return_value={"included_in_attack_budget": False}), \
                 patch.object(full.pilot, "run_batched", side_effect=generate), \
                 patch.object(full.torch.cuda, "empty_cache"):
                result = full.run_experiment(out, config, selection, None, None, "cpu")
            self.assertEqual(len(generated), 25)
            self.assertEqual(loaded_targets, config["target_models"])
            self.assertEqual(len(result["summary"]), 78)
            self.assertEqual(len(result["comparisons"]), 90)
            self.assertEqual(result["total_sample_view_gradient_evaluations"], 11300)
            self.assertEqual(sum(job["seed"] is None for job in result["jobs"]), 7)
            self.assertTrue((out / "comparisons.csv").is_file())
            self.assertTrue((out / "completion.json").is_file())


if __name__ == "__main__":
    unittest.main()
