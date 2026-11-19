"""Statistical/input safeguards using synthetic predictions only."""
import csv
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from course_tools import v1_multiplicity as multiplicity


def fixture(directory):
    """Two BSR methods, two MI baselines, one target, deliberately shuffled IDs."""
    ids = [31, 10, 75, 8, 6, 9, 51, 11, 81, 77, 41, 3, 2, 5, 22, 47]
    methods = {
        "bsr_m2_g40": {"method": "bsr", "seeds": [42, 142, 242], "gradient_budget": 40},
        "bsr_m4_g40": {"method": "bsr", "seeds": [42, 142, 242], "gradient_budget": 40},
        "mi_g40": {"method": "mi", "seeds": [None], "gradient_budget": 40},
        "mi_g40_fixed_step": {"method": "mi", "seeds": [None], "gradient_budget": 40},
    }
    target = "synthetic_target"
    rows, successes = [], {}
    clean = np.array([0] * 15 + [1])
    for method_index, (name, metadata) in enumerate(methods.items()):
        saved = []
        for seed_index, seed in enumerate(metadata["seeds"]):
            adv = np.array([int((i + method_index + seed_index) % (method_index + 2) == 0) for i in range(16)])
            saved.append(adv != 0)
            for image_id, clean_pred, adv_pred in zip(ids, clean, adv):
                rows.append({"target": target, "method": name, "seed": seed, "test_id": image_id,
                             "label": 0, "clean_prediction": int(clean_pred),
                             "adversarial_prediction": int(adv_pred), "gradient_budget": 40})
        successes[name] = np.stack(saved)[:, clean == 0].mean(axis=0)
    comparisons = []
    for first, second in (("bsr_m2_g40", "mi_g40"), ("bsr_m2_g40", "mi_g40_fixed_step"),
                          ("bsr_m4_g40", "mi_g40"), ("bsr_m4_g40", "mi_g40_fixed_step"),
                          ("bsr_m4_g40", "bsr_m2_g40")):
        comparisons.append({"target": target, "subset": "full1000", "method_a": first, "method_b": second,
                            "gradient_budget": 40, "asr_denominator": 15,
                            "asr_a": float(successes[first].mean()), "asr_b": float(successes[second].mean()),
                            "difference_a_minus_b": float((successes[first] - successes[second]).mean()),
                            "ci95": [-0.3, 0.3]})
    results = {"targets": {target: {}}, "methods": methods, "subsets": {"full1000": 16}, "comparisons": comparisons}
    selection = {"final_ids": ids, "subsets": {"full1000": list(range(16))}}
    for filename, content in (("results.json", results), ("selection.json", selection),
                              ("config.frozen.json", {"batch_size": 4})):
        (directory / filename).write_text(json.dumps(content), encoding="utf-8")
    rewrite_rows(directory, rows)
    return rows, results


def rewrite_rows(directory, rows):
    with (directory / "predictions.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class MultiplicityTests(unittest.TestCase):
    def test_holm_and_bh_known_values_preserve_original_order(self):
        pvalues = [0.01, 0.04, 0.03, 0.002]
        np.testing.assert_allclose(multiplicity.adjust_pvalues(pvalues, "holm"), [0.03, 0.06, 0.06, 0.008])
        np.testing.assert_allclose(multiplicity.adjust_pvalues(pvalues, "fdr_bh"), [0.02, 0.04, 0.04, 0.008])

    def test_adjustment_handles_ties_and_probability_bounds(self):
        pvalues = [0.0, 0.01, 0.01, 1.0]
        np.testing.assert_allclose(multiplicity.adjust_pvalues(pvalues, "holm"), [0.0, 0.03, 0.03, 1.0])
        np.testing.assert_allclose(multiplicity.adjust_pvalues(pvalues, "fdr_bh"), [0.0, 0.04/3, 0.04/3, 1.0])
        self.assertEqual(multiplicity.adjust_pvalues([0.4], "holm").tolist(), [0.4])

    def test_invalid_pvalue_inputs_are_rejected(self):
        for values in ([], [-0.1], [1.1], [np.nan], [np.inf], [[0.1]]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                multiplicity.adjust_pvalues(values, "holm")
        with self.assertRaises(ValueError):
            multiplicity.adjust_pvalues([0.1], "not_a_method")

    def test_cluster_sandwich_matches_manual_two_batch_calculation(self):
        # Mean=.5; cluster residual sums +1,-1; variance=2/(2-1)*2/4^2=.25.
        result = multiplicity.cluster_summary([1, 1, 0, 0], [0, 0, 1, 1])
        self.assertAlmostEqual(result["difference_a_minus_b"], 0.5)
        self.assertAlmostEqual(result["cluster_standard_error"], 0.5)
        self.assertEqual(result["degrees_of_freedom"], 1)
        self.assertEqual(result["clean_correct_count"], 4)
        self.assertEqual(result["inference_status"], "ok")

    def test_nonestimable_cases_do_not_invent_zero_pvalues(self):
        one_cluster = multiplicity.cluster_summary([0, 1], [4, 4])
        zero_variance = multiplicity.cluster_summary([1, 1], [4, 7])
        self.assertEqual(one_cluster["inference_status"], "insufficient_clusters")
        self.assertIsNone(one_cluster["cluster_standard_error"])
        self.assertEqual(zero_variance["inference_status"], "zero_cluster_variance")
        self.assertEqual(zero_variance["cluster_standard_error"], 0)

    def test_constant_fraction_roundoff_cannot_create_fake_tiny_variance(self):
        result = multiplicity.cluster_summary(np.full(15, 1/3), np.repeat([0, 1, 2], 5))
        self.assertEqual(result["inference_status"], "zero_cluster_variance")
        self.assertEqual(result["cluster_standard_error"], 0.0)

    def test_dynamic_family_includes_available_comparisons_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            self.assertEqual(len(multiplicity.inspect_run(root)["comparisons"]), 4)
            self.assertEqual(len(multiplicity.inspect_run(root, family="all")["comparisons"]), 5)

    def test_csv_reordering_is_aligned_by_id_and_seed_rows_are_averaged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, _ = fixture(root)
            context = multiplicity.inspect_run(root)
            before = multiplicity.load_predictions(context)
            difference, groups = multiplicity.pair_data(context, before, context["comparisons"][0])
            self.assertEqual(len(difference), 15)  # Not 3*15 independent seed rows.
            self.assertAlmostEqual(float(difference.mean()), context["comparisons"][0]["difference_a_minus_b"])
            self.assertEqual(groups.tolist(), [0]*4 + [1]*4 + [2]*4 + [3]*3)
            rewrite_rows(root, rows[::-1])
            context = multiplicity.inspect_run(root)
            after = multiplicity.load_predictions(context)
            actual, actual_groups = multiplicity.pair_data(context, after, context["comparisons"][0])
            np.testing.assert_array_equal(actual, difference)
            np.testing.assert_array_equal(actual_groups, groups)

    def test_changed_csv_after_inspection_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, _ = fixture(root)
            context = multiplicity.inspect_run(root)
            rewrite_rows(root, rows[::-1])
            with self.assertRaisesRegex(ValueError, "changed after"):
                multiplicity.load_predictions(context)

    def test_repeated_seed_outcomes_do_not_inflate_image_count_or_shrink_se(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, results = fixture(root)
            before = multiplicity.inspect_run(root)
            predictions = multiplicity.load_predictions(before)
            d, groups = multiplicity.pair_data(before, predictions, before["comparisons"][0])
            summary_before = multiplicity.cluster_summary(d, groups)
            copies = []
            for name, metadata in results["methods"].items():
                if metadata["method"] == "bsr":
                    copies.extend([{**row, "seed": row["seed"] + 1000} for row in rows if row["method"] == name])
                    metadata["seeds"] += [seed + 1000 for seed in metadata["seeds"]]
            rows.extend(copies)
            rewrite_rows(root, rows)
            (root / "results.json").write_text(json.dumps(results), encoding="utf-8")
            after = multiplicity.inspect_run(root)
            predictions = multiplicity.load_predictions(after)
            d, groups = multiplicity.pair_data(after, predictions, after["comparisons"][0])
            self.assertEqual(multiplicity.cluster_summary(d, groups), summary_before)

    def test_duplicate_missing_or_unexpected_ids_are_rejected(self):
        for kind in ("duplicate", "missing", "unexpected"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                rows, _ = fixture(root)
                if kind == "duplicate":
                    rows.append(rows[0].copy())
                elif kind == "missing":
                    rows.pop()
                else:
                    rows[0]["test_id"] = 999
                rewrite_rows(root, rows)
                with self.assertRaises(ValueError):
                    multiplicity.load_predictions(multiplicity.inspect_run(root))

    def test_inconsistent_labels_clean_predictions_or_seeds_are_rejected(self):
        for field, value in (("label", 1), ("clean_prediction", 1), ("seed", 999)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                rows, _ = fixture(root)
                rows[0][field] = value
                rewrite_rows(root, rows)
                with self.assertRaises(ValueError):
                    multiplicity.load_predictions(multiplicity.inspect_run(root))

    def test_missing_entire_attack_seed_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, _ = fixture(root)
            rows = [row for row in rows if not (row["method"] == "bsr_m2_g40" and row["seed"] == 142)]
            rewrite_rows(root, rows)
            with self.assertRaisesRegex(ValueError, "Missing prediction"):
                multiplicity.load_predictions(multiplicity.inspect_run(root))

    def test_stored_point_difference_or_denominator_mismatch_is_rejected(self):
        for key, value in (("difference_a_minus_b", 0.99), ("asr_denominator", 100)):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fixture(root)
                context = multiplicity.inspect_run(root)
                predictions = multiplicity.load_predictions(context)
                comparison = {**context["comparisons"][0], key: value}
                with self.assertRaises(ValueError):
                    multiplicity.pair_data(context, predictions, comparison)

    def test_recorded_hash_changes_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "completion.json").write_text(json.dumps({"sha256": {"predictions.csv": "0"*64}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                multiplicity.inspect_run(root)

    def test_plan_lists_family_without_inference_or_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            output = root / "analysis_not_created"
            captured = io.StringIO()
            with patch.object(multiplicity, "analyse", side_effect=AssertionError("inference must not run")), redirect_stdout(captured):
                self.assertEqual(multiplicity.main(["--run", str(root), "--plan", "--output", str(output)]), 0)
            plan = json.loads(captured.getvalue())
            self.assertEqual(plan["family_size"], 4)
            self.assertFalse(plan["inference_performed"])
            self.assertFalse(output.exists())

    def test_existing_output_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / "user_work.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                multiplicity.write_report(output, {})
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
