"""Report safeguards using explicit synthetic fixtures, never experiment data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt

from course_tools import report_v1_full as report


def fixture_results():
    targets = {name: {"full_test_clean": {"accuracy": 0.9, "correct": 9000, "count": 10000}}
               for name in ("cifar10_mobilenetv2_x1_0", "cifar10_vgg11_bn")}
    methods = {"mi10_reference": {"method": "mi", "steps": 10, "views": 1, "gradient_budget": 10}}
    for budget in report.BUDGETS:
        for views in (1, 2, 4):
            name = f"mi_g{budget}" if views == 1 else f"bsr_m{views}_g{budget}"
            methods[name] = {"method": "mi" if views == 1 else "bsr", "steps": budget // views,
                             "views": views, "gradient_budget": budget}
        methods[f"mi_g{budget}_fixed_step"] = {"method": "mi", "steps": budget, "views": 1, "gradient_budget": budget}
    rows, comparisons = [], []
    for target in targets:
        for subset, count in (("full1000", 1000), ("new800", 800), ("pilot200", 200)):
            for name, metadata in methods.items():
                per_seed = ([{"seed": seed, "asr": value} for seed, value in zip((42, 142, 242), (0.69, 0.70, 0.71))]
                            if metadata["method"] == "bsr" else [{"seed": None, "asr": 0.7}])
                rows.append({**metadata, "target": target, "subset": subset, "method": name,
                             "alpha": 0.001, "alpha_kind": "test_fixture", "attack_seed_count": len(per_seed),
                             "clean_accuracy": 0.9, "robust_accuracy": 0.27, "asr_numerator": count*0.9*0.7,
                             "asr_denominator": int(count*0.9), "asr": 0.7, "asr_seed_min": min(x["asr"] for x in per_seed),
                             "asr_seed_max": max(x["asr"] for x in per_seed), "source_asr": 0.98,
                             "mean_attack_seconds": metadata["gradient_budget"] / 10, "per_seed": per_seed})
            for budget in report.BUDGETS:
                for views in (2, 4):
                    for suffix in ("", "_fixed_step"):
                        comparisons.append({"target": target, "subset": subset,
                                            "method_a": f"bsr_m{views}_g{budget}", "method_b": f"mi_g{budget}{suffix}",
                                            "gradient_budget": budget, "difference_a_minus_b": 0.01, "ci95": [-0.02, 0.04]})
    return {"schema_version": 2, "stage": "full", "completed_at": "2026-11-18T12:00:00+08:00",
            "source": "cifar10_resnet20", "targets": targets, "methods": methods, "summary": rows,
            "comparisons": comparisons, "api_calls": 0, "jobs": []}


def write_fixture(directory):
    results = fixture_results()
    selection = {"final_ids": list(range(1000)), "pilot_ids": list(range(200)), "new_ids": list(range(200, 1000))}
    for name, value in (("config.frozen.json", {}), ("selection.json", selection), ("results.json", results)):
        report.write_json(directory / name, value)
    report.write_json(directory / "provenance.json", {
        "config_sha256": report.sha256(directory / "config.frozen.json"),
        "selection_sha256": report.sha256(directory / "selection.json"),
    })
    for name in ("summary.csv", "per_seed.csv", "predictions.csv", "comparisons.csv"):
        (directory / name).write_text("synthetic_unit_test_fixture\n", encoding="utf-8")
    report.write_json(directory / "completion.json", {
        "completed_at": results["completed_at"],
        "sha256": {name: report.sha256(directory / name) for name in ("results.json", "summary.csv")},
    })
    return results


class FullReportTests(unittest.TestCase):
    def test_interval_crossing_zero_does_not_claim_equivalence_or_advantage(self):
        text = report.comparison_description({"difference_a_minus_b": 0.02, "ci95": [-0.03, 0.07]})
        self.assertIn("包含零", text)
        self.assertIn("不能确定", text)
        self.assertNotIn("等价", text)
        self.assertEqual(report.interval_text([-0.03, 0.07]), "[-3.00, +7.00]")

    def test_methods_and_missing_metrics_are_labeled_correctly(self):
        self.assertEqual(report.human_method("mi_g40_fixed_step"), "MI G=40, α=ε/10")
        self.assertEqual(report.human_method("bsr_m2_g80"), "BSR M=2, G=80")
        self.assertEqual(report.pct(None), "N/A")
        self.assertEqual(report.comparison_description({"difference_a_minus_b": None, "ci95": None}), "分母不足，无法计算差值或区间")

    def test_time_figures_use_mean_cost_not_sum_and_keep_full1000_cost_for_new800(self):
        captured = {}

        def capture(fig, destination, name):
            if name.startswith("asr_vs_time"):
                captured[name] = [list(line.get_xdata()) for line in fig.axes[0].lines]
            plt.close(fig)

        with patch.object(report, "save_figure", side_effect=capture):
            report.plot_budget_and_time(fixture_results(), Path("unused_fixture_output"))
        self.assertEqual(captured["asr_vs_time_full1000"][1], [2.0, 4.0, 8.0])
        self.assertEqual(captured["asr_vs_time_new800"][1], [2.0, 4.0, 8.0])

    def test_complete_frozen_matrix_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            results, _, _, selection = report.validate_run(root)
            self.assertEqual(len(results["summary"]), 78)
            self.assertEqual(len(selection["new_ids"]), 800)

    def test_changed_recorded_metric_or_frozen_config_is_rejected(self):
        for filename in ("summary.csv", "config.frozen.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_fixture(root)
                (root / filename).write_text('{"changed": true}\n', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    report.validate_run(root)

    def test_missing_bsr_seed_is_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = write_fixture(root)
            row = next(row for row in results["summary"] if row["method"] == "bsr_m2_g40")
            row["per_seed"] = row["per_seed"][:2]
            report.write_json(root / "results.json", results)
            marker = report.load_json(root / "completion.json")
            marker["sha256"]["results.json"] = report.sha256(root / "results.json")
            report.write_json(root / "completion.json", marker)
            with self.assertRaisesRegex(ValueError, "Missing seeds"):
                report.validate_run(root)

    def test_existing_report_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            existing = root / "already_reviewed_report"
            existing.mkdir()
            (existing / "note.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                report.export_report(root, existing)
            self.assertEqual((existing / "note.txt").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
