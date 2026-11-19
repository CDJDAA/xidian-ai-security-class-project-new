"""Dataset-selection checks, independent of model predictions and downloads."""
import unittest
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from course_tools.run_v1 import ROOT, attack_configs, read_config, selection_manifest


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.config = read_config(ROOT / "configs/v1_budget.json")
        self.data = SimpleNamespace(targets=[label for label in range(10) for _ in range(1000)])

    def test_pilot_is_balanced_fixed_subset_of_predeclared_final_ids(self):
        result = selection_manifest(self.data, self.data, self.config)
        pilot, final = result["pilot_ids"], result["final_ids"]
        self.assertEqual(len(pilot), 200)
        self.assertEqual(len(final), 1000)
        self.assertEqual(len(set(final)), 1000)
        self.assertTrue(set(pilot) <= set(final))
        for label in range(10):
            self.assertEqual(sum(self.data.targets[index] == label for index in pilot), 20)
            self.assertEqual(sum(self.data.targets[index] == label for index in final), 100)
        self.assertEqual(result, selection_manifest(self.data, self.data, self.config))

    def test_selection_uses_labels_without_reading_any_images_or_predictions(self):
        class LabelsOnly:
            targets = self.data.targets

            def __getitem__(self, index):
                raise AssertionError("Selection must not inspect image/model outputs")

        result = selection_manifest(LabelsOnly(), LabelsOnly(), self.config)
        self.assertEqual(len(result["development_ids"]), 50)

    def test_declared_equal_budget_and_sensitivity_comparisons_are_valid(self):
        methods = {cfg.name: cfg for cfg in attack_configs(self.config)}
        primary, bsr, sensitivity = [methods[name] for name in (
            "mi40_g40", "bsr10x4_g40", "mi40_g40_large_step"
        )]
        self.assertEqual({cfg.steps * cfg.views for cfg in (primary, bsr, sensitivity)}, {40})
        self.assertEqual(primary.method, "mi")
        self.assertEqual(bsr.method, "bsr")
        self.assertEqual(sensitivity.alpha, bsr.alpha)
        self.assertAlmostEqual(primary.alpha * primary.steps, bsr.alpha * bsr.steps)

    def test_incomplete_or_invalid_protocol_fails_before_model_execution(self):
        for key, value in (("batch_size", 1.5), ("bootstrap_replicates", 0), ("attack_seed", -1)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                config = {**self.config, key: value}
                path = Path(directory) / "invalid.json"
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read_config(path)
        with tempfile.TemporaryDirectory() as directory:
            config = {**self.config, "methods": self.config["methods"][:-1]}
            path = Path(directory) / "incomplete.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "all four"):
                read_config(path)


if __name__ == "__main__":
    unittest.main()
