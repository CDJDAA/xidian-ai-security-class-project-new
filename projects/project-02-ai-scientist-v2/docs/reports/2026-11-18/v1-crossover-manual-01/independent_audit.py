"""Independent, read-only audit of the saved manual V1 run and derived tables.

Uses only the standard library and NumPy. It does not import project analysis
helpers, torch, model code, or attack code. Only --output is written.

Scope matches the original stdin audit: 252 paired point differences and CRV1
SEs/denominators/cluster counts/df, Holm adjustment within three 84-test families,
five added M2-minus-M4 image-bootstrap intervals, all translated CSV records,
and the six original completion hashes. This does not independently recompute
Student-t tail probabilities, BH, or every confidence interval.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run, report):
    result = read_json(run / "results.json")
    selection = read_json(run / "selection.json")
    manifest = read_json(report / "analysis.json")
    with (report / "data/all_comparisons.csv").open(encoding="utf-8-sig", newline="") as stream:
        comparisons = list(csv.DictReader(stream))
    assert len(comparisons) == 252

    ids = selection["final_ids"]
    count = len(ids)
    assert count == 1000 and len(set(ids)) == count
    positions_by_id = {image_id: position for position, image_id in enumerate(ids)}
    labels = np.full(count, -1, dtype=int)
    clean = {target: np.full(count, -1, dtype=int) for target in result["targets"]}
    adversarial = {}
    with (run / "predictions.csv").open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["target"], row["method"], None if row["seed"] == "" else int(row["seed"]))
            position = positions_by_id[int(row["test_id"])]
            adversarial.setdefault(key, np.full(count, -1, dtype=int))[position] = int(row["adversarial_prediction"])
            labels[position] = int(row["label"])
            clean[key[0]][position] = int(row["clean_prediction"])
    assert len(adversarial) == 112
    assert all((values >= 0).all() for values in adversarial.values())

    # Each saved attack contributes one success indicator per image. Average
    # attack seeds first, rather than treating S*N rows as independent images.
    per_image_means = {}
    for target in result["targets"]:
        for name, metadata in result["methods"].items():
            successes = np.stack([adversarial[(target, name, seed)] for seed in metadata["seeds"]]) != labels
            per_image_means[(target, name)] = successes.mean(axis=0)

    seen = set()
    max_point_error, max_se_error = 0.0, 0.0
    family_sizes = {}
    for row in comparisons:
        target, subset, first, second = (row[key] for key in ("target", "subset", "method_a", "method_b"))
        key = (target, subset, first, second)
        assert key not in seen, key
        seen.add(key)
        positions = np.asarray(selection["subsets"][subset], dtype=int)
        clean_correct = clean[target][positions] == labels[positions]
        difference = (per_image_means[(target, first)] - per_image_means[(target, second)])[positions][clean_correct]
        point = difference.mean()
        groups = positions[clean_correct] // 20
        unique_groups = np.unique(groups)
        group_count, denominator = len(unique_groups), len(difference)
        residual_sums = np.array([np.sum(difference[groups == group] - point) for group in unique_groups])
        standard_error = np.sqrt((group_count / (group_count - 1)) * np.sum(residual_sums * residual_sums) / denominator**2)
        point_error = abs(point - float(row["difference_a_minus_b"]))
        se_error = abs(standard_error - float(row["cluster_standard_error"]))
        assert point_error < 1e-12, (key, point, row["difference_a_minus_b"])
        assert se_error < 1e-12, (key, standard_error, row["cluster_standard_error"])
        assert denominator == int(row["asr_denominator"]), key
        assert group_count == int(row["cluster_count"]), key
        assert group_count - 1 == int(row["degrees_of_freedom"]), key
        assert int(row["multiplicity_family_size"]) == 84, key
        max_point_error = max(max_point_error, float(point_error))
        max_se_error = max(max_se_error, float(se_error))
        family_sizes[subset] = family_sizes.get(subset, 0) + 1

    # Independently apply the Holm step-down rule to the recorded raw p-values.
    # This checks grouping and adjustment, not the Student-t tail calculation.
    for subset in family_sizes:
        rows = [row for row in comparisons if row["subset"] == subset]
        assert len(rows) == 84
        ordered = sorted(rows, key=lambda row: float(row["p_raw_cluster_t"]))
        previous = 0.0
        for index, row in enumerate(ordered):
            adjusted = min(1.0, max(previous, (84 - index) * float(row["p_raw_cluster_t"])))
            previous = adjusted
            assert abs(adjusted - float(row["p_holm"])) < 1e-13, (subset, index)
            assert (row["reject_holm"] == "True") == (adjusted <= 0.05), (subset, index)

    # Unlike the project helper's batched resampling, draw the full index matrix
    # at once. Keep the same estimator, seed, repetition count, and quantiles.
    bootstrap_checks = []
    for target, budget in [
        ("cifar10_mobilenetv2_x1_0", 20),
        ("cifar10_mobilenetv2_x1_0", 80),
        ("cifar10_vgg11_bn", 20),
        ("cifar10_vgg11_bn", 40),
        ("cifar10_vgg11_bn", 80),
    ]:
        first, second = f"bsr_m2_g{budget}", f"bsr_m4_g{budget}"
        row = next(row for row in comparisons if row["subset"] == "full1000" and row["target"] == target and row["method_a"] == first and row["method_b"] == second)
        clean_correct = clean[target] == labels
        per_image_difference = (per_image_means[(target, first)] - per_image_means[(target, second)]) * clean_correct
        draws = np.random.default_rng(20261117).integers(0, count, size=(10000, count))
        values = per_image_difference[draws].sum(axis=1) / clean_correct[draws].sum(axis=1)
        interval = np.quantile(values, [0.025, 0.975])
        stored = [float(row["ci95_lower"]), float(row["ci95_upper"])]
        assert np.allclose(interval, stored, rtol=0, atol=1e-12), (target, budget, interval, stored)
        bootstrap_checks.append({"target": target, "gradient_budget": budget, "method_a": first, "method_b": second, "subset": "full1000", "ci95": interval.tolist(), "matches": True})
        del draws

    # Retain every record, value, and source ordering; only the declared header
    # and explanatory text mappings may differ in the Chinese CSV copies.
    translated_files = {
        "summary.csv": "方法汇总_中文.csv",
        "per_seed.csv": "种子明细_中文.csv",
        "comparisons.csv": "原配对比较_中文.csv",
        "predictions.csv": "完整逐图预测_中文.csv",
    }
    translated_row_counts = {}
    for original, chinese in translated_files.items():
        with (run / original).open(encoding="utf-8", newline="") as source, (report / "data" / chinese).open(encoding="utf-8-sig", newline="") as translated:
            source_reader, translated_reader = csv.DictReader(source), csv.DictReader(translated)
            rows = 0
            for left, right in zip(source_reader, translated_reader, strict=True):
                for key, value in left.items():
                    column = manifest["headers_cn"][key]
                    if original == "per_seed.csv" and key == "asr_numerator":
                        column = "该种子攻击成功图片数"
                    if key == "target":
                        value = manifest["target_names"][value]
                    elif key == "subset":
                        value = manifest["subset_names"][value]
                    elif key == "alpha_kind":
                        value = {"fixed_epsilon_over_denominator": "固定步长ε/10", "epsilon_over_steps": "按更新步数ε/T"}[value]
                    elif key == "timing_scope":
                        value = "完整1000张每种子生成；跨目标与集合复用；不含预热和评价"
                    elif key == "resampling_unit":
                        value = "按图片配对抽样，保留全部方法与攻击种子"
                    elif key == "in_pilot200":
                        value = "是" if value == "True" else "否"
                    assert right[column] == value, (original, rows, key, value, right[column])
                rows += 1
            translated_row_counts[original] = rows
    assert translated_row_counts == {"summary.csv": 168, "per_seed.csv": 336, "comparisons.csv": 168, "predictions.csv": 112000}

    completion = read_json(run / "completion.json")
    original_hashes = {}
    for name, expected in completion["sha256"].items():
        actual = sha256(run / name)
        assert actual == expected, name
        original_hashes[name] = actual

    return {
        "status": "passed",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_directory": str(run),
        "report_directory": str(report),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "audit_script_sha256": sha256(Path(__file__)),
        "point_differences_checked": len(comparisons),
        "cluster_standard_errors_checked": len(comparisons),
        "denominators_cluster_counts_and_df_checked": len(comparisons),
        "max_point_difference_error": max_point_error,
        "max_standard_error_difference": max_se_error,
        "family_sizes": family_sizes,
        "holm_adjustments_checked": len(comparisons),
        "additional_image_bootstrap_intervals_checked": bootstrap_checks,
        "bootstrap_seed": 20261117,
        "bootstrap_repetitions": 10000,
        "translated_records_fully_preserved": translated_row_counts,
        "original_completion_sha256_preserved": original_hashes,
        "input_report_sha256": {
            "analysis.json": sha256(report / "analysis.json"),
            "data/all_comparisons.csv": sha256(report / "data/all_comparisons.csv"),
            **{"data/" + name: sha256(report / "data" / name) for name in translated_files.values()},
        },
        "scope": "Independent numerical and preservation audit only; no project metric or multiplicity helpers imported.",
        "not_independently_checked": [
            "Student-t tail probabilities behind the recorded raw p-values",
            "BH adjusted p-values",
            "All 252 confidence intervals (five newly added M2-minus-M4 intervals were independently resampled)",
            "Model predictions by rerunning classifiers",
            "Adversarial tensors by regenerating attacks",
        ],
        "model_inference_calls": 0,
        "attacks_generated": 0,
        "api_calls": 0,
        "torch_imported": "torch" in sys.modules,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    args = parser.parse_args()
    run, report, output = args.run.resolve(), args.report.resolve(), args.output.resolve()
    assert run.is_dir() and report.is_dir()
    # Source files and directories must never be used as the JSON destination.
    assert not output.is_relative_to(run) and not output.is_relative_to(report)
    result = audit(run, report)
    assert result["torch_imported"] is False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "point_differences_checked": 252, "cluster_standard_errors_checked": 252, "holm_adjustments_checked": 252, "bootstrap_intervals_checked": 5, "translated_prediction_rows": result["translated_records_fully_preserved"]["predictions.csv"], "model_inference_calls": 0, "attacks_generated": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
