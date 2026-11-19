"""Read-only exploratory resampling of saved V1 attack predictions."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "uncertainty-sensitivity.json"
REPEATS = 5000
SEED = 20261118
ATTACK_SEEDS = [42, 142, 242]

selection = json.loads((ROOT / "selection.json").read_text(encoding="utf-8"))
original = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))
final_ids = selection["final_ids"]
assert len(final_ids) == len(set(final_ids)) == 1000
by_job = {}
with (ROOT / "predictions.csv").open(encoding="utf-8", newline="") as stream:
    for row in csv.DictReader(stream):
        key = (row["target"], row["method"], row["seed"])
        by_job.setdefault(key, {})[int(row["test_id"])] = row
assert all(set(rows) == set(final_ids) for rows in by_job.values())
old_comparisons = {
    (row["target"], row["subset"], row["method_a"], row["method_b"]): row
    for row in original["comparisons"]
}
targets = ["cifar10_mobilenetv2_x1_0", "cifar10_vgg11_bn"]


def get_arrays(target, method, seed):
    rows = by_job[(target, method, "" if seed is None else str(seed))]
    clean = np.array([int(rows[i]["clean_prediction"]) == int(rows[i]["label"]) for i in final_ids])
    success = np.array([int(rows[i]["adversarial_prediction"]) != int(rows[i]["label"]) for i in final_ids]) & clean
    return clean, success.astype(float)


def interval(values):
    valid = values[np.isfinite(values)]
    return [float(x) for x in np.quantile(valid, [0.025, 0.975])]


results = []
streams = np.random.SeedSequence(SEED).spawn(4)
for subset_index, subset in enumerate(["full1000", "new800"]):
    selected_ids = set(final_ids if subset == "full1000" else selection["new_ids"])
    positions = np.array([i for i, sample in enumerate(final_ids) if sample in selected_ids])
    batch_ids = positions // 20
    nonempty_batches = np.unique(batch_ids)
    group_positions = [positions[batch_ids == group] for group in nonempty_batches]
    k = len(group_positions)
    # Batch and whole-attack-seed streams are independent. The same draws are
    # paired across all comparisons within this subset for sensitivity analysis.
    batch_rng = np.random.default_rng(streams[subset_index * 2])
    seed_rng = np.random.default_rng(streams[subset_index * 2 + 1])
    batch_weights = batch_rng.multinomial(k, np.full(k, 1 / k), size=REPEATS)
    seed_weights = seed_rng.multinomial(3, np.full(3, 1 / 3), size=REPEATS) / 3
    for target in targets:
        for budget in [40, 80]:
            for views in [2, 4]:
                method_a = f"bsr_m{views}_g{budget}"
                bsr_arrays = [get_arrays(target, method_a, s) for s in ATTACK_SEEDS]
                clean = bsr_arrays[0][0]
                assert all(np.array_equal(clean, arr[0]) for arr in bsr_arrays)
                bsr = np.stack([arr[1] for arr in bsr_arrays])
                for fixed in [False, True]:
                    method_b = f"mi_g{budget}" + ("_fixed_step" if fixed else "")
                    mi_clean, mi = get_arrays(target, method_b, None)
                    assert np.array_equal(clean, mi_clean)
                    denominator = int(clean[positions].sum())
                    seed_asr = bsr[:, positions].sum(axis=1) / denominator
                    mi_asr = float(mi[positions].sum() / denominator)
                    point = float(seed_asr.mean() - mi_asr)
                    old = old_comparisons[(target, subset, method_a, method_b)]
                    assert abs(point - old["difference_a_minus_b"]) < 1e-12
                    assert denominator == old["asr_denominator"]
                    seed_deltas = seed_asr - mi_asr
                    loo_deltas = (seed_asr.sum() - seed_asr) / 2 - mi_asr
                    cluster_d = np.array([clean[p].sum() for p in group_positions])
                    cluster_mi = np.array([mi[p].sum() for p in group_positions])
                    cluster_bsr = np.stack([bsr[:, p].sum(axis=1) for p in group_positions])
                    boot_d = batch_weights @ cluster_d
                    boot_mi = batch_weights @ cluster_mi
                    boot_bsr = batch_weights @ cluster_bsr
                    batch_only = (boot_bsr.mean(axis=1) - boot_mi) / boot_d
                    crossed = ((boot_bsr * seed_weights).sum(axis=1) - boot_mi) / boot_d
                    assert np.all(boot_d > 0)
                    row = {
                        "target": target, "subset": subset,
                        "method_a": method_a, "method_b": method_b,
                        "gradient_budget": budget, "views": views,
                        "sample_count": len(positions), "clean_correct_count": denominator,
                        "nonempty_original_batches": k,
                        "subset_images_per_nonempty_batch": {"min": min(map(len, group_positions)), "max": max(map(len, group_positions))},
                        "asr_a": float(seed_asr.mean()), "asr_b": mi_asr,
                        "difference_a_minus_b": point,
                        "matches_original_point_estimate": True,
                        "original_image_ci95": old["ci95"],
                        "batch_only_ci95": interval(batch_only),
                        "batch_and_whole_seed_ci95": interval(crossed),
                        "per_seed_difference": {str(s): float(x) for s, x in zip(ATTACK_SEEDS, seed_deltas)},
                        "per_seed_difference_range": [float(seed_deltas.min()), float(seed_deltas.max())],
                        "leave_one_seed_out_difference": {str(s): float(x) for s, x in zip(ATTACK_SEEDS, loo_deltas)},
                        "leave_one_seed_out_difference_range": [float(loo_deltas.min()), float(loo_deltas.max())],
                        "bootstrap_repetitions": REPEATS,
                        "zero_denominator_repetitions": int(np.sum(boot_d == 0)),
                    }
                    row["percentage_points"] = {
                        key: [float(x * 100) for x in row[key]] if isinstance(row[key], list) else float(row[key] * 100)
                        for key in ["difference_a_minus_b", "original_image_ci95", "batch_only_ci95", "batch_and_whole_seed_ci95", "per_seed_difference_range", "leave_one_seed_out_difference_range"]
                    }
                    results.append(row)

assert len(results) == 32
payload = {
    "purpose": "Exploratory sensitivity analysis of saved predictions only; no attack generation, model inference, or target gradients.",
    "limitations": [
        "Only three existing BSR attack seeds are available. Seed resampling is exploratory and is not a substitute for more independent attack seeds or a fresh held-out evaluation.",
        "These intervals do not replace the original intervals and must not be described as a formal correction or as definitive more reliable final confidence intervals.",
        "Results remain conditional on the fixed data/model choices. Full1000 and new800 overlap; new800 excludes pilot200 but does not constitute a fresh target model.",
        "Batch resampling reflects shared per-batch BSR transforms in this implementation; only original nonempty batches in the selected subset are resampled.",
    ],
    "method": {
        "bootstrap_repetitions": REPEATS, "bootstrap_seed": SEED,
        "original_batch_size": 20, "attack_seeds": ATTACK_SEEDS,
        "clusters": "Original final_ids position // 20; retain nonempty clusters in each subset; resample K clusters with replacement.",
        "seed_resampling": "Resample three whole BSR attack seeds with replacement, one common seed-weight vector across all resampled batches in a replicate; independent of cluster resampling. MI remains one fixed deterministic outcome vector.",
        "estimator": "Difference between BSR mean clean-correct attack success and MI clean-correct attack success; recalculate clean-correct denominator for every cluster bootstrap replicate.",
        "interval": "2.5th/97.5th percentile of 5000 bootstrap estimates; no multiplicity correction.",
        "shared_draws": "Draws shared across comparisons within each subset; independent streams for batches and seeds and between subsets.",
    },
    "input_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ["results.json", "selection.json", "predictions.csv"]},
    "comparisons": results,
}
OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(str(OUT))
for row in results:
    if row["views"] == 2 and (("mobilenet" in row["target"] and row["method_b"].endswith("fixed_step")) or ("vgg" in row["target"] and row["gradient_budget"] == 80 and not row["method_b"].endswith("fixed_step"))):
        print(json.dumps({key: row[key] for key in ["target", "subset", "method_a", "method_b", "nonempty_original_batches", "percentage_points"]}))

