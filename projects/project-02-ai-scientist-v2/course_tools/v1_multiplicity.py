"""Read-only, conditional multiplicity sensitivity analysis of saved V1 results.

This module never imports torch or runs an attack/model. It keeps one difference
per image after averaging each attack's saved seeds, then uses the ORIGINAL
generation batches as clusters. Holm-adjusted p-values are the main result;
BH p-values are exploratory. Bonferroni cluster-t intervals are a different,
approximate simultaneous-interval procedure, not "Holm/BH confidence intervals".
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


INPUT_FILES = ("results.json", "predictions.csv", "selection.json", "config.frozen.json")
NOTES = [
    "Post-hoc sensitivity analysis of saved predictions; not a new confirmatory experiment.",
    "Conditional on these fixed models, image IDs, batches, and realized attack seeds. Seed rows are averaged within image, never treated as independent images.",
    "Cluster sandwich SE and Student-t inference are large-cluster approximations, not exact finite-sample guarantees; degrees of freedom equal nonempty clean-correct clusters minus one.",
    "Holm controls family-wise error for valid component p-values under arbitrary test dependence. Its validity here inherits the approximate component tests.",
    "BH is exploratory: FDR control requires independent or suitably positively dependent valid tests; that dependence condition has not been established for this experiment.",
    "Bonferroni cluster-t intervals are approximate simultaneous intervals. They are not Holm intervals or BH intervals and do not replace the saved image-bootstrap intervals.",
    "Failure to reject zero difference does not prove equivalence, no difference, or equal performance.",
    "Unavailable tests retain a conservative p=1 placeholder during family adjustment, but exported raw/adjusted p-values and decisions for those tests remain null.",
    "Full1000, pilot200 and new800 overlap. Each invocation defines one subset family; running them separately does not create independent confirmations or control a combined family.",
]
REFERENCES = {
    "multipletests": "https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html",
    "family_error_and_dependence": "https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html",
    "cluster_covariance": "https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html",
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def adjust_pvalues(pvalues, method):
    """Holm or BH adjustment in original order, including tied p-values."""
    pvalues = np.asarray(pvalues, dtype=float)
    if pvalues.ndim != 1 or not len(pvalues) or not np.isfinite(pvalues).all() or ((pvalues < 0) | (pvalues > 1)).any():
        raise ValueError("p-values must be a nonempty finite one-dimensional array in [0,1]")
    order = np.argsort(pvalues, kind="stable")
    ordered = pvalues[order]
    count = len(ordered)
    if method == "holm":
        adjusted = np.maximum.accumulate(ordered * np.arange(count, 0, -1))
    elif method == "fdr_bh":
        scaled = ordered * count / np.arange(1, count + 1)
        adjusted = np.minimum.accumulate(scaled[::-1])[::-1]
    else:
        raise ValueError("method must be holm or fdr_bh")
    result = np.empty(count)
    result[order] = np.minimum(adjusted, 1.0)
    return result


def cluster_summary(differences, groups):
    """Intercept-only CRV1 covariance, with one observation per eligible image."""
    values = np.asarray(differences, dtype=float)
    groups = np.asarray(groups)
    if values.ndim != 1 or groups.ndim != 1 or values.shape != groups.shape or not len(values):
        raise ValueError("differences and groups must be matching nonempty vectors")
    if not np.isfinite(values).all() or groups.dtype.kind not in "iu" or (groups < 0).any():
        raise ValueError("Invalid differences or integer cluster IDs")
    unique, inverse = np.unique(groups, return_inverse=True)
    count, cluster_count = len(values), len(unique)
    difference = float(values.mean())
    result = {
        "difference_a_minus_b": difference,
        "clean_correct_count": count,
        "cluster_count": cluster_count,
        "degrees_of_freedom": cluster_count - 1,
        "cluster_standard_error": None,
        "inference_status": "insufficient_clusters",
    }
    if cluster_count < 2:
        return result
    if np.ptp(values) == 0:
        # Constant fractions such as 1/3 can have a rounded mean differing by
        # one ULP. Their true residual variance is still zero, not tiny-positive.
        result["cluster_standard_error"] = 0.0
        result["inference_status"] = "zero_cluster_variance"
        return result
    residual_sums = np.bincount(inverse, weights=values - difference)
    variance = cluster_count / (cluster_count - 1) * float(residual_sums @ residual_sums) / count**2
    standard_error = float(np.sqrt(variance))
    result["cluster_standard_error"] = standard_error
    result["inference_status"] = "ok" if standard_error > 0 else "zero_cluster_variance"
    return result


def inspect_run(run, subset="full1000", family="bsr_vs_mi"):
    """Read metadata and select the entire recorded family, without inference."""
    if family not in ("bsr_vs_mi", "all"):
        raise ValueError("family must be bsr_vs_mi or all")
    run = Path(run).resolve()
    hashes = {name: sha256(run / name) for name in INPUT_FILES}
    # Original raw runs and curated reports use different checksum manifests.
    for filename, key in (("completion.json", "sha256"), ("verification.json", "artifacts_sha256")):
        if (run / filename).exists():
            recorded = read_json(run / filename).get(key, {})
            for name, digest in hashes.items():
                if name in recorded and digest != recorded[name]:
                    raise ValueError(f"Recorded input hash mismatch: {name}")
    results = read_json(run / "results.json")
    selection = read_json(run / "selection.json")
    config = read_json(run / "config.frozen.json")
    final_ids = selection["final_ids"]
    if not final_ids or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in final_ids) or len(set(final_ids)) != len(final_ids):
        raise ValueError("final_ids must be nonempty, unique nonnegative integers")
    positions = selection.get("subsets", {}).get(subset)
    if positions is None:
        # Also accept older selection records containing ID lists only.
        if subset == "full1000":
            positions = list(range(len(final_ids)))
        else:
            field = {"pilot200": "pilot_ids", "new800": "new_ids"}.get(subset)
            selected_ids = selection.get(field, []) if field else []
            if not selected_ids or len(set(selected_ids)) != len(selected_ids) or not set(selected_ids) <= set(final_ids):
                raise ValueError(f"Unknown or invalid selection subset: {subset}")
            chosen = set(selected_ids)
            positions = [i for i, sample in enumerate(final_ids) if sample in chosen]
    if not positions or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(final_ids) for i in positions) or len(set(positions)) != len(positions):
        raise ValueError(f"Invalid subset positions: {subset}")
    if results.get("subsets", {}).get(subset, len(positions)) != len(positions):
        raise ValueError("Subset size differs between results and selection")
    batch_size = positive_int(config["batch_size"], "batch_size")
    methods = results["methods"]
    targets = list(results["targets"])
    if not targets or len(set(targets)) != len(targets) or not methods:
        raise ValueError("Missing or duplicate targets/methods")
    for name, metadata in methods.items():
        seeds = metadata["seeds"]
        if not seeds or len(set(seeds)) != len(seeds):
            raise ValueError(f"Missing or duplicate seeds: {name}")
        if metadata["method"] == "mi":
            if seeds != [None]:
                raise ValueError(f"Deterministic MI must be recorded once: {name}")
        elif metadata["method"] == "bsr":
            if any(isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 for seed in seeds):
                raise ValueError(f"Invalid BSR seeds: {name}")
        else:
            raise ValueError(f"Unsupported method type: {name}")
    comparisons, seen = [], set()
    for row in results["comparisons"]:
        if row["subset"] != subset:
            continue
        if row["target"] not in targets or row["method_a"] not in methods or row["method_b"] not in methods:
            raise ValueError("Comparison references an unknown target or method")
        kinds = {methods[row[key]]["method"] for key in ("method_a", "method_b")}
        if family == "bsr_vs_mi" and kinds != {"bsr", "mi"}:
            continue
        key = (row["target"], row["method_a"], row["method_b"])
        if key in seen:
            raise ValueError(f"Duplicate comparison: {key}")
        seen.add(key)
        finite_number(row["difference_a_minus_b"], "saved difference")
        interval = row.get("ci95")
        if interval is not None:
            if not isinstance(interval, list) or len(interval) != 2 or finite_number(interval[0], "CI lower") > finite_number(interval[1], "CI upper"):
                raise ValueError("Invalid saved bootstrap interval")
        comparisons.append(row)
    if not comparisons:
        raise ValueError(f"No recorded comparisons for subset={subset}, family={family}")
    return {
        "run": run, "results": results, "config": config, "selection": selection,
        "positions": np.asarray(positions, dtype=int), "batch_size": batch_size,
        "comparisons": comparisons, "subset": subset, "family": family,
        "input_sha256": hashes,
    }


def load_predictions(context):
    """Validate every recorded job, aligning by test_id rather than CSV order."""
    if sha256(context["run"] / "predictions.csv") != context["input_sha256"]["predictions.csv"]:
        raise ValueError("Prediction CSV changed after metadata inspection")
    results, selection = context["results"], context["selection"]
    ids = selection["final_ids"]
    id_set = set(ids)
    expected = {(target, name, seed) for target in results["targets"]
                for name, metadata in results["methods"].items() for seed in metadata["seeds"]}
    rows, labels, clean = {}, {}, {}
    required = {"target", "method", "seed", "test_id", "label", "clean_prediction", "adversarial_prediction"}
    with (context["run"] / "predictions.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Missing required prediction CSV columns")
        for row in reader:
            seed = None if row["seed"] == "" else int(row["seed"])
            job = (row["target"], row["method"], seed)
            if job not in expected:
                raise ValueError(f"Unexpected target/method/seed in prediction CSV: {job}")
            image_id = int(row["test_id"])
            if image_id not in id_set:
                raise ValueError(f"Unexpected test_id: {image_id}")
            job_rows = rows.setdefault(job, {})
            if image_id in job_rows:
                raise ValueError(f"Duplicate test_id within prediction job: {job}, {image_id}")
            label, clean_prediction, adv = (int(row[key]) for key in ("label", "clean_prediction", "adversarial_prediction"))
            if any(value < 0 or value > 9 for value in (label, clean_prediction, adv)):
                raise ValueError("CIFAR10 prediction classes must be integers in [0,9]")
            if labels.setdefault(image_id, label) != label:
                raise ValueError(f"Inconsistent label across prediction rows: {image_id}")
            clean_key = (job[0], image_id)
            if clean.setdefault(clean_key, clean_prediction) != clean_prediction:
                raise ValueError(f"Inconsistent clean prediction across methods/seeds: {clean_key}")
            if "gradient_budget" in row and int(row["gradient_budget"]) != results["methods"][job[1]]["gradient_budget"]:
                raise ValueError("Prediction gradient budget differs from recorded method")
            job_rows[image_id] = adv
    if set(rows) != expected or any(set(job_rows) != id_set for job_rows in rows.values()):
        raise ValueError("Missing prediction jobs, seeds, or test IDs")
    if sha256(context["run"] / "predictions.csv") != context["input_sha256"]["predictions.csv"]:
        raise ValueError("Prediction CSV changed while reading")
    label_array = np.asarray([labels[i] for i in ids])
    return {
        "labels": label_array,
        "clean": {target: np.asarray([clean[(target, i)] for i in ids]) for target in results["targets"]},
        "adversarial": {job: np.asarray([job_rows[i] for i in ids]) for job, job_rows in rows.items()},
        "row_count": sum(len(job_rows) for job_rows in rows.values()),
    }


def pair_data(context, predictions, comparison):
    """Compute the saved estimand, checking the denominator and point estimate."""
    target = comparison["target"]
    positions = context["positions"]
    labels = predictions["labels"][positions]
    correct = predictions["clean"][target][positions] == labels
    if not correct.any():
        raise ValueError(f"No clean-correct images for {target}/{context['subset']}")
    means = []
    for key in ("method_a", "method_b"):
        name = comparison[key]
        seeds = context["results"]["methods"][name]["seeds"]
        attacks = np.stack([predictions["adversarial"][(target, name, seed)][positions] for seed in seeds])
        means.append((attacks[:, correct] != labels[correct]).mean(axis=0))
    difference = means[0] - means[1]
    count = int(correct.sum())
    if not np.isclose(float(difference.mean()), comparison["difference_a_minus_b"], rtol=0, atol=1e-12):
        raise ValueError(f"Saved point difference does not match prediction CSV: {comparison['method_a']}/{comparison['method_b']}")
    if comparison.get("asr_denominator", count) != count:
        raise ValueError("Saved clean-correct denominator does not match predictions")
    for key, values in zip(("asr_a", "asr_b"), means):
        if key in comparison and not np.isclose(float(values.mean()), comparison[key], rtol=0, atol=1e-12):
            raise ValueError(f"Saved {key} does not match predictions")
    groups = (positions // context["batch_size"])[correct]
    return difference, groups


def analyse(context, alpha=0.05):
    """Conditional cluster-t tests plus explicitly separate multiplicity outputs."""
    alpha = finite_number(alpha, "alpha")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0,1)")
    try:
        from scipy import __version__ as scipy_version
        from scipy.stats import t
    except ImportError as error:
        raise RuntimeError("SciPy is required for cluster-t inference; --plan needs no SciPy. In the project virtual environment, run: python -m pip install -r requirements-v1-analysis.txt. This tool never installs packages.") from error
    predictions = load_predictions(context)
    family_size = len(context["comparisons"])
    rows = []
    for comparison in context["comparisons"]:
        values, groups = pair_data(context, predictions, comparison)
        summary = cluster_summary(values, groups)
        row = {key: comparison[key] for key in ("target", "subset", "method_a", "method_b", "gradient_budget")}
        row.update(summary)
        row.update({
            "original_image_bootstrap_ci95": comparison.get("ci95"),
            "p_raw_cluster_t": None, "p_holm": None, "p_bh_exploratory": None,
            "reject_holm": None, "reject_bh_exploratory": None,
            "bonferroni_cluster_t_simultaneous_ci": None,
            "attack_seed_count_a": len(context["results"]["methods"][row["method_a"]]["seeds"]),
            "attack_seed_count_b": len(context["results"]["methods"][row["method_b"]]["seeds"]),
            "few_clusters_warning": summary["cluster_count"] < 30,
        })
        if summary["inference_status"] == "ok":
            standard_error, df = summary["cluster_standard_error"], summary["degrees_of_freedom"]
            raw = float(2 * t.sf(abs(summary["difference_a_minus_b"] / standard_error), df))
            row["p_raw_numerically_floored"] = raw == 0.0
            row["p_raw_cluster_t"] = max(raw, float(np.nextafter(0.0, 1.0)))
            critical = float(t.ppf(1 - alpha / (2 * family_size), df))
            margin = critical * standard_error
            row["bonferroni_cluster_t_simultaneous_ci"] = [summary["difference_a_minus_b"] - margin, summary["difference_a_minus_b"] + margin]
        rows.append(row)
    conservative_p = [row["p_raw_cluster_t"] if row["p_raw_cluster_t"] is not None else 1.0 for row in rows]
    holm, bh = adjust_pvalues(conservative_p, "holm"), adjust_pvalues(conservative_p, "fdr_bh")
    for index, row in enumerate(rows):
        if row["p_raw_cluster_t"] is not None:
            row.update({"p_holm": float(holm[index]), "p_bh_exploratory": float(bh[index]),
                        "reject_holm": bool(holm[index] <= alpha), "reject_bh_exploratory": bool(bh[index] <= alpha)})
    return {
        "analysis": "Conditional cluster-t multiplicity sensitivity analysis",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_directory": str(context["run"]), "subset": context["subset"], "family": context["family"],
        "family_size": family_size, "alpha": alpha, "simultaneous_confidence_level": 1 - alpha,
        "input_sha256": context["input_sha256"], "analysis_script_sha256": sha256(__file__),
        "prediction_rows_validated": predictions["row_count"], "original_batch_size": context["batch_size"],
        "method": "d_i=mean_s success_a(s,i)-mean_s success_b(s,i), restricted to target clean-correct images; delta=mean_i d_i. Cluster g=original final_ids position // original batch size. CRV1 variance=G/(G-1)*sum_g(sum_i_in_g(d_i-delta))^2/N^2, Student-t df=G-1. Holm is primary; BH exploratory. Separate Bonferroni intervals use t critical value at 1-alpha/(2*family_size).",
        "numpy_version": np.__version__, "scipy_version": scipy_version, "notes": NOTES, "references": REFERENCES,
        "model_inference_calls": 0, "attacks_generated": 0, "api_calls": 0,
        "comparisons": rows,
    }


def write_report(output, result):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "multiplicity.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    flat = []
    for row in result["comparisons"]:
        value = {key: value for key, value in row.items() if key not in ("original_image_bootstrap_ci95", "bonferroni_cluster_t_simultaneous_ci")}
        for field in ("original_image_bootstrap_ci95", "bonferroni_cluster_t_simultaneous_ci"):
            interval = row[field]
            value[f"{field}_lower"] = interval[0] if interval is not None else None
            value[f"{field}_upper"] = interval[1] if interval is not None else None
        flat.append(value)
    columns = list(dict.fromkeys(key for row in flat for key in row))
    with (output / "multiplicity.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(flat)

    def number(value):
        return "N/A" if value is None else f"{value:.4g}"

    lines = [
        "# V1 多重比较敏感性检查", "",
        f"集合：`{result['subset']}`；家族：`{result['family']}`；共 {result['family_size']} 个记录中的对照；α={result['alpha']}。", "",
        "这是对已观察数据的事后敏感性检查，条件于当前模型和已有攻击种子，不是新实验或独立确认。每张图先平均种子，再按原生成 batch 聚类；没有把三个种子乘成三倍图片。", "",
        "主结果是 Holm 校正后的近似 cluster-t p 值。原图片 bootstrap 区间与另算的 Bonferroni cluster-t 近似同时区间均保留在 JSON/CSV；它们不是 Holm/BH 区间。BH 仅作探索，其依赖条件未在本实验中验证。不拒绝零差异不等于证明等效或无差异。", "",
        "| 目标 | 方法 A − B | ΔASR／百分点 | 原始 p | Holm p | BH p（探索） | Holm 拒绝零差异 | 状态 |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in result["comparisons"]:
        decision = "N/A" if row["reject_holm"] is None else ("是" if row["reject_holm"] else "否")
        lines.append(f"| {row['target']} | {row['method_a']} − {row['method_b']} | {100 * row['difference_a_minus_b']:+.2f} | {number(row['p_raw_cluster_t'])} | {number(row['p_holm'])} | {number(row['p_bh_exploratory'])} | {decision} | {row['inference_status']} |")
    lines.extend(["", "只有一个有效 cluster 或 cluster 方差为零时不报告确定的 p 值；相关行保留在家族大小中。正差值表示 A 的 ASR 更高，拒绝零差异本身不表示差异方向为正。", "", "完整条件、输入 SHA256、各对照有效图片数与 batch 数见 [JSON](multiplicity.json)；便于查看的表格见 [CSV](multiplicity.csv)。", "", "该目录为新建分析输出；未修改原始结果或重新运行模型、攻击。", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path, help="Existing raw run or curated report containing all four input files")
    parser.add_argument("--subset", default="full1000")
    parser.add_argument("--family", choices=("bsr_vs_mi", "all"), default="bsr_vs_mi")
    parser.add_argument("--output", type=Path, help="A new directory; existing directories are never overwritten")
    parser.add_argument("--plan", action="store_true", help="List the recorded family only; no inference or output files")
    args = parser.parse_args(argv)
    context = inspect_run(args.run, args.subset, args.family)
    if args.plan:
        plan = {"subset": args.subset, "family": args.family, "family_size": len(context["comparisons"]),
                "input_sha256": context["input_sha256"], "inference_performed": False,
                "prediction_rows_validated": False,
                "comparisons": [{key: row[key] for key in ("target", "subset", "method_a", "method_b", "gradient_budget")} for row in context["comparisons"]]}
        print(json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    if args.output is None:
        parser.error("--output is required unless --plan is used")
    if args.output.exists():
        raise FileExistsError(f"Output directory already exists: {args.output}")
    result = analyse(context)
    write_report(args.output, result)
    print(f"V1_MULTIPLICITY_COMPLETE family={result['family_size']} output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
