"""Configurable exploratory V1 sweeps, separate from the frozen full matrix.

Use --plan to inspect actual steps, views, alpha, seed jobs and gradient cost
without assets, model inference or attack generation. Image selection remains
the original 1000 IDs; changing selection requires a separate study protocol.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
from datetime import datetime
import io
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import numpy as np
import torch

from course_tools import run_v1 as pilot
from course_tools import run_v1_full as full
from course_tools.v1_assets import MODEL_SPECS, load_cifar, load_model, prepare_assets
from course_tools.v1_attacks import AttackConfig
from course_tools.v1_metrics import paired_bootstrap, summarise_predictions

ROOT = Path(__file__).resolve().parents[1]
STAGE = "exploratory_sweep"
# Freeze the executable dependency chain, independently of prose or old report
# renderers. Editing a teaching guide must not invalidate an interrupted sweep.
SOURCE_FILES = (
    "course_tools/run_v1_sweep.py", "course_tools/run_v1_full.py",
    "course_tools/run_v1.py", "course_tools/v1_assets.py",
    "course_tools/v1_attacks.py", "course_tools/v1_metrics.py",
)
PRIOR_ACCESS = (
    "Exploratory settings may be chosen after observing the original V1 target results. "
    "The original full1000 and new800 have already had attack effects evaluated. "
    "Within this run all source-only attacks finish before target-effect evaluation. "
    "This is not a fresh held-out confirmation."
)


def read_config(path):
    """Validate a flexible matrix before any runtime or asset initialization."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("schema_version") != 2 or config.get("dataset") != "CIFAR10":
        raise ValueError("Unsupported sweep configuration")
    if config.get("stage") != STAGE:
        raise ValueError(f"Sweep stage must be {STAGE}")
    for key in ("sample_count", "batch_size", "blocks", "fixed_step_denominator", "bootstrap_replicates"):
        full.positive_integer(config[key], key)
    if config["sample_count"] != 1000:
        raise ValueError("This sweep reuses exactly 1000 inherited images")
    for key in ("epsilon", "clean_accuracy_floor"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 1:
            raise ValueError(f"Invalid {key}")
    if config["blocks"] > 32:
        raise ValueError("CIFAR blocks cannot exceed the 32-pixel image dimensions")
    if not re.fullmatch(r"[a-f0-9]{64}", config["selection_sha256"]):
        raise ValueError("Missing full SHA256 for inherited selection")
    targets = config["target_models"]
    if not isinstance(targets, list) or not 1 <= len(targets) <= 2 or len(set(targets)) != len(targets):
        raise ValueError("Use one or two distinct target models")
    if config["source_model"] in targets:
        raise ValueError("Source must be distinct from targets")
    if any(name not in MODEL_SPECS for name in [config["source_model"], *targets]):
        raise ValueError("Source or target is not supported by the verified asset registry")
    budgets, views = config["gradient_budgets"], config["views"]
    for key, values in (("gradient_budgets", budgets), ("views", views)):
        if not isinstance(values, list) or not values:
            raise ValueError(f"{key} must be a nonempty list")
        for value in values:
            full.positive_integer(value, key)
        if len(set(values)) != len(values):
            raise ValueError(f"Duplicate {key}")
    if 1 not in views or not any(view > 1 for view in views):
        raise ValueError("views must include MI view 1 and at least one BSR view count > 1")
    for budget in budgets:
        for view in views:
            if budget % view:
                raise ValueError(f"Budget G={budget} must be divisible by M={view}; do not round G/M")
    rules = config["mi_step_rules"]
    if not isinstance(rules, list) or not rules or len(set(rules)) != len(rules) or any(rule not in ("fixed", "epsilon_over_steps") for rule in rules):
        raise ValueError("mi_step_rules must select fixed and/or epsilon_over_steps without duplicates")
    seeds = config["bsr_seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise ValueError("At least one BSR base seed is required")
    for seed in [*seeds, config["bootstrap_seed"]]:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63 - 1000:
            raise ValueError("Invalid seed")
    if len(set(seeds)) != len(seeds):
        raise ValueError("BSR base seeds must be distinct")
    batches = (config["sample_count"] + config["batch_size"] - 1) // config["batch_size"]
    if any(second - first < batches for first, second in zip(sorted(seeds), sorted(seeds)[1:])):
        raise ValueError("BSR base-seed streams would overlap across batches")
    build_methods(config)
    return config


def build_methods(config):
    """Translate each exact budget G into integer T and M, then an AttackConfig."""
    methods = []

    def add(name, kind, steps, views, alpha, alpha_kind):
        attack = AttackConfig(name, kind, steps, views, config["epsilon"], alpha,
                              decay=config["momentum_decay"], blocks=config["blocks"],
                              rotation_degrees=config["rotation_degrees"])
        methods.append({**asdict(attack), "gradient_budget": steps * views,
                        "alpha_kind": alpha_kind,
                        "seeds": config["bsr_seeds"][:] if kind == "bsr" else [None]})

    for budget in config["gradient_budgets"]:
        for rule in config["mi_step_rules"]:
            fixed = rule == "fixed"
            add(f"mi_g{budget}" + ("_fixed_step" if fixed else ""), "mi", budget, 1,
                config["epsilon"] / (config["fixed_step_denominator"] if fixed else budget),
                "fixed_epsilon_over_denominator" if fixed else "epsilon_over_steps")
        for views in (value for value in config["views"] if value > 1):
            if budget % views:
                raise ValueError(f"Budget G={budget} must be divisible by M={views}; do not round G/M")
            steps = budget // views
            add(f"bsr_m{views}_g{budget}", "bsr", steps, views,
                config["epsilon"] / steps, "epsilon_over_steps")
    return methods


def comparison_pairs(methods, budget):
    selected = [method for method in methods if method["gradient_budget"] == budget]
    return [(bsr["name"], mi["name"]) for bsr in selected if bsr["method"] == "bsr"
            for mi in selected if mi["method"] == "mi"]


def make_plan(config):
    methods = build_methods(config)
    jobs = full.build_jobs(methods)
    by_name = {method["name"]: method for method in methods}
    return {"stage": STAGE, "sample_count": config["sample_count"],
            "source_model": config["source_model"], "target_models": config["target_models"],
            "methods": methods, "jobs": jobs, "generation_jobs": len(jobs),
            "mi_generation_jobs": sum(job["seed"] is None for job in jobs),
            "bsr_generation_jobs": sum(job["seed"] is not None for job in jobs),
            "total_sample_view_gradient_evaluations": config["sample_count"] * sum(by_name[job["method"]]["gradient_budget"] for job in jobs),
            "comparisons_per_target_subset": sum(len(comparison_pairs(methods, budget)) for budget in config["gradient_budgets"]),
            "budget_scope": "Attack generation only; warmup and model evaluation are recorded separately",
            "prior_access": PRIOR_ACCESS, "api_calls": 0}


def load_selection(config, test):
    selection = full.load_selection(config, test)
    selection["inherited_selection_rule"] = selection.get("rule")
    selection["rule"] = "Original label-stratified IDs preserved; previously observed V1 target results can inform this exploratory sweep, which is not a held-out confirmation."
    selection["new800_definition"] = "Excludes only the initial pilot200; the full1000 and these 800 images have already had attack effects evaluated in the original V1 run."
    selection["selection_policy"] = "Original final_ids and exact order reused for an exploratory sweep; no new held-out evaluation set"
    return selection


def prepare_run(out, config, selection, assets, *, resume=False, source_root=ROOT, source_files=SOURCE_FILES, env=None):
    provenance = full.prepare_run(out, config, selection, assets, resume=resume,
                                  source_root=source_root, source_files=source_files, env=env)
    if resume:
        if provenance.get("stage") != STAGE or provenance.get("target_access") != PRIOR_ACCESS:
            raise ValueError("Resume provenance is not this exploratory sweep")
    else:
        provenance.update(stage=STAGE, target_access=PRIOR_ACCESS)
        full.atomic_json(Path(out) / "provenance.json", provenance)
    return provenance


def run_experiment(out, config, selection, train, test, device):
    """Generate every source attack first, then evaluate saved attacks on targets."""
    methods = build_methods(config)
    by_name = {method["name"]: method for method in methods}
    jobs = full.build_jobs(methods)
    ids = selection["final_ids"]
    images, labels = pilot.load_tensors(test, ids)
    input_path = out / "inputs.pt"
    if input_path.exists():
        saved = torch.load(input_path, map_location="cpu", weights_only=True)
        if saved["ids"] != ids or not torch.equal(saved["images"], images) or not torch.equal(saved["labels"], labels):
            raise ValueError("Frozen input cache differs from dataset")
    else:
        torch.save({"images": images, "labels": labels, "ids": ids}, input_path)
    dev_images, dev_labels = pilot.load_tensors(train, selection["development_ids"])
    source = load_model(config["source_model"], ROOT, device)
    source_full_clean = pilot.full_clean_accuracy(source, test, 128, device)
    if source_full_clean["accuracy"] < config["clean_accuracy_floor"]:
        raise RuntimeError("Source clean accuracy below floor")
    source_clean = pilot.predict(source, images, config["batch_size"], device)
    warming = full.warmup(source, dev_images, dev_labels, config, device)
    job_results = []
    for number, job in enumerate(jobs, start=1):
        method = by_name[job["method"]]
        cached = full.load_cached_job(out, job, method, images, labels, ids)
        print(f"JOB {number}/{len(jobs)} {job['job_id']} {'cache verified' if cached else 'generating'}", flush=True)
        if cached is None:
            settings = {**config, "attack_seed": job["seed"] if job["seed"] is not None else config["bsr_seeds"][0]}
            with redirect_stdout(io.StringIO()):
                adversarial, generation = pilot.run_batched(source, images, labels, full.attack_config(method), settings, device, job["job_id"])
            predicted = pilot.predict(source, adversarial, config["batch_size"], device)
            payload = {"adversarial": adversarial, "ids": ids, "labels": labels,
                       "source_predictions": torch.from_numpy(predicted),
                       "linf": (adversarial - images).abs().flatten(1).amax(1)}
            full.validate_payload(payload, images, labels, ids, method)
            generation.update(method=method["name"], seed=job["seed"], job_id=job["job_id"])
            full.save_cached_job(out, job, method, payload, generation)
        else:
            payload, generation = cached
        job_results.append({**job, "cache_path": f"cache/{job['job_id']}.pt", "generation": generation})
        full.atomic_json(out / "progress.json", {"completed_jobs": number, "total_jobs": len(jobs), "last_job": job["job_id"], "updated_at": pilot.timestamp()})
        print(f"DONE {job['job_id']} {generation['attack_seconds']:.3f}s G={method['gradient_budget']}", flush=True)
        del payload
    del source
    torch.cuda.empty_cache()
    for method in methods:
        per_seed = [item["generation"] for item in job_results if item["method"] == method["name"]]
        method["generation"] = {"per_seed": per_seed,
                                "mean_attack_seconds": float(np.mean([item["attack_seconds"] for item in per_seed])),
                                "total_attack_seconds": float(sum(item["attack_seconds"] for item in per_seed)),
                                "max_peak_cuda_allocated_mib": max(item["peak_cuda_allocated_mib"] for item in per_seed)}
    target_started_at = pilot.timestamp()
    full.atomic_json(out / "target_evaluation_started.json", {"at": target_started_at, "all_generation_jobs_completed": len(job_results)})
    target_results, summary, seed_rows, prediction_rows, comparisons = {}, [], [], [], []
    pilot_ids = set(selection["pilot_ids"])
    for target_name in config["target_models"]:
        print(f"TARGET {target_name}: all attacks already generated", flush=True)
        target = load_model(target_name, ROOT, device)
        target_full_clean = pilot.full_clean_accuracy(target, test, 128, device)
        if target_full_clean["accuracy"] < config["clean_accuracy_floor"]:
            raise RuntimeError(f"Target clean accuracy below floor: {target_name}")
        clean = pilot.predict(target, images, config["batch_size"], device)
        target_results[target_name] = {"full_test_clean": target_full_clean, "evaluation_started_at": pilot.timestamp()}
        method_predictions, method_source_predictions = {}, {}
        for method in methods:
            adversarial_predictions, source_predictions = [], []
            cache_method = {key: value for key, value in method.items() if key != "generation"}
            for job in (item for item in jobs if item["method"] == method["name"]):
                payload, _ = full.load_cached_job(out, job, cache_method, images, labels, ids)
                predicted = pilot.predict(target, payload["adversarial"], config["batch_size"], device)
                adversarial_predictions.append(predicted)
                source_prediction = payload["source_predictions"].numpy()
                source_predictions.append(source_prediction)
                for position, image_id in enumerate(ids):
                    prediction_rows.append({"target": target_name, "method": method["name"], "seed": job["seed"],
                                            "test_id": image_id, "label": int(labels[position]),
                                            "clean_prediction": int(clean[position]), "adversarial_prediction": int(predicted[position]),
                                            "source_clean_prediction": int(source_clean[position]), "source_adversarial_prediction": int(source_prediction[position]),
                                            "gradient_budget": method["gradient_budget"], "linf": float(payload["linf"][position]),
                                            "in_pilot200": image_id in pilot_ids})
                del payload
            method_predictions[method["name"]] = np.stack(adversarial_predictions)
            method_source_predictions[method["name"]] = np.stack(source_predictions)
        for subset, positions in selection["subsets"].items():
            index = np.asarray(positions)
            y = labels.numpy()[index]
            for method in methods:
                metrics = summarise_predictions(y, clean[index], method_predictions[method["name"]][:, index])
                source_metrics = summarise_predictions(y, source_clean[index], method_source_predictions[method["name"]][:, index])
                for per_seed, actual_seed in zip(metrics["per_seed"], method["seeds"]):
                    per_seed["seed"] = actual_seed
                row = {"target": target_name, "subset": subset, "method": method["name"],
                       "steps": method["steps"], "views": method["views"], "gradient_budget": method["gradient_budget"],
                       "alpha": method["alpha"], "alpha_kind": method["alpha_kind"], **metrics,
                       **full.seed_spread(metrics), "source_asr": source_metrics["asr"],
                       "mean_attack_seconds": method["generation"]["mean_attack_seconds"],
                       "timing_scope": "Whole selected set generation cost per seed, reused across targets and subsets; not subset-specific timing"}
                summary.append(row)
                for position, per_seed in enumerate(metrics["per_seed"]):
                    seed_rows.append({**{key: row[key] for key in ("target", "subset", "method", "steps", "views", "gradient_budget", "alpha", "alpha_kind")},
                                      **per_seed, "source_asr": source_metrics["per_seed"][position]["asr"],
                                      "attack_seconds": method["generation"]["per_seed"][position]["attack_seconds"]})
            for budget in config["gradient_budgets"]:
                for first, second in comparison_pairs(methods, budget):
                    compared = paired_bootstrap(y, clean[index], method_predictions[first][:, index], method_predictions[second][:, index],
                                                seed=config["bootstrap_seed"], n_bootstrap=config["bootstrap_replicates"])
                    comparisons.append({"target": target_name, "subset": subset, "method_a": first, "method_b": second,
                                        "gradient_budget": budget, **compared})
        del target
        torch.cuda.empty_cache()
    expected = len(ids) * sum(by_name[job["method"]]["gradient_budget"] for job in jobs)
    actual = sum(item["generation"]["sample_view_gradient_evaluations"] for item in job_results)
    if actual != expected:
        raise RuntimeError("Sweep actual gradient total differs from matrix")
    results = {"schema_version": 2, "stage": STAGE, "completed_at": pilot.timestamp(), "images": len(ids),
               "source": config["source_model"], "source_full_test_clean": source_full_clean, "targets": target_results,
               "target_evaluation_started_at": target_started_at,
               "subsets": {name: len(values) for name, values in selection["subsets"].items()},
               "methods": {method["name"]: method for method in methods}, "jobs": job_results,
               "summary": summary, "comparisons": comparisons, "warmup": warming,
               "total_sample_view_gradient_evaluations": actual, "api_calls": 0,
               "limitations": [PRIOR_ACCESS,
                               f"One pretrained source and {len(config['target_models'])} pretrained targets; not independent training repeats",
                               f"{len(config['bsr_seeds'])} real BSR seed streams; deterministic MI runs once per configuration; no best-of-seeds",
                               "Paired image intervals are conditional on fixed weights and realized seeds, with no multiplicity correction",
                               "Batch-shared geometry and CUDA rotation backward can limit bitwise reproducibility",
                               "Equal gradient evaluations do not imply equal FLOPs or wall time; timing is descriptive"]}
    pilot.write_csv(out / "summary.csv", [{key: value for key, value in row.items() if key != "per_seed"} for row in summary])
    pilot.write_csv(out / "per_seed.csv", seed_rows)
    pilot.write_csv(out / "predictions.csv", prediction_rows)
    pilot.write_csv(out / "comparisons.csv", [{**{key: value for key, value in row.items() if key != "ci95"},
                                               "ci95_lower": row["ci95"][0] if row["ci95"] else None,
                                               "ci95_upper": row["ci95"][1] if row["ci95"] else None} for row in comparisons])
    full.atomic_json(out / "results.json", results)
    full.atomic_json(out / "completion.json", {"completed_at": results["completed_at"], "sha256": {
        name: pilot.sha256(out / name) for name in ("results.json", "summary.csv", "per_seed.csv", "predictions.csv", "comparisons.csv", "inputs.pt")}})
    if (out / "failure.json").exists():
        history = out / "failure_history"
        history.mkdir(exist_ok=True)
        (out / "failure.json").replace(history / f"recovered_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.json")
    print(f"V1_SWEEP_COMPLETED {out} gradients={actual:,}", flush=True)
    return results


def verify_completed_run(out, config, selection, test):
    completion = json.loads((out / "completion.json").read_text(encoding="utf-8"))
    for filename, expected in completion["sha256"].items():
        if pilot.sha256(out / filename) != expected:
            raise ValueError("Completed result checksum mismatch")
    images, labels = pilot.load_tensors(test, selection["final_ids"])
    for method in build_methods(config):
        for job in full.build_jobs([method]):
            if full.load_cached_job(out, job, method, images, labels, selection["final_ids"]) is None:
                raise ValueError("Completed run is missing a completed attack cache")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/v1_crossover.json")
    parser.add_argument("--plan", action="store_true", help="Print exact matrix and costs, then exit without assets or inference")
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--output", type=Path)
    location.add_argument("--resume", type=Path)
    args = parser.parse_args(argv)
    config = read_config(args.config.resolve())
    if args.plan:
        print(json.dumps(make_plan(config), ensure_ascii=False, indent=2))
        return
    device = pilot.setup_runtime()
    assets = prepare_assets(ROOT, download=False)
    train = load_cifar(ROOT, train=True, download=False)
    test = load_cifar(ROOT, train=False, download=False)
    selection = load_selection(config, test)
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
    out = (args.resume or args.output or ROOT / "experiments" / f"v1_sweep_{stamp}").resolve()
    prepare_run(out, config, selection, assets, resume=args.resume is not None)
    if args.resume and (out / "completion.json").exists():
        verify_completed_run(out, config, selection, test)
        print(f"V1_SWEEP_ALREADY_COMPLETED_AND_VERIFIED {out}", flush=True)
        return
    try:
        run_experiment(out, config, selection, train, test, device)
    except Exception as error:
        full.atomic_json(out / "failure.json", {"failed_at": pilot.timestamp(), "type": type(error).__name__, "message": str(error)})
        raise


if __name__ == "__main__":
    main()
