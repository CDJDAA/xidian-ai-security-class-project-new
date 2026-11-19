"""Frozen multi-budget, multi-seed and multi-target V1 experiment.

The fixed pilot remains independently reproducible through run_v1.py. This
entrypoint reuses its reviewed attack and prediction helpers, generates all
source-only attacks before evaluating targets, and preserves validated caches.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from dataclasses import asdict
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
from zoneinfo import ZoneInfo

import numpy as np
import torch
import torchvision

from course_tools import run_v1 as pilot
from course_tools.v1_assets import MODEL_SPECS, load_cifar, load_model, prepare_assets
from course_tools.v1_attacks import AttackConfig
from course_tools.v1_metrics import paired_bootstrap, summarise_predictions

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "course_tools/run_v1_full.py", "course_tools/run_v1.py",
    "course_tools/v1_assets.py", "course_tools/v1_attacks.py",
    "course_tools/v1_metrics.py", "course_tools/report_v1_full.py",
    "docs/research/v1-full-protocol.md",
)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    pilot.dump_json(temporary, value)
    temporary.replace(path)


def positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")


def read_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config["schema_version"] != 2 or config["dataset"] != "CIFAR10":
        raise ValueError("Unsupported full V1 configuration")
    for key in ("sample_count", "batch_size", "blocks", "fixed_step_denominator", "bootstrap_replicates"):
        positive_integer(config[key], key)
    if config["sample_count"] != 1000:
        raise ValueError("The frozen full V1 evaluation contains exactly 1000 images")
    if not 0 < config["epsilon"] <= 1 or not 0 < config["clean_accuracy_floor"] <= 1:
        raise ValueError("Invalid epsilon or clean accuracy floor")
    if not re.fullmatch(r"[a-f0-9]{64}", config["selection_sha256"]):
        raise ValueError("Missing full SHA256 for inherited selection")
    if config["gradient_budgets"] != [20, 40, 80] or config["views"] != [1, 2, 4]:
        raise ValueError("This predeclared matrix requires G=20/40/80 and M=1/2/4")
    if len(config["target_models"]) != 2 or len(set(config["target_models"])) != 2:
        raise ValueError("Exactly two distinct target models are required")
    if config["source_model"] in config["target_models"]:
        raise ValueError("Source must be distinct from targets")
    if any(name not in MODEL_SPECS for name in [config["source_model"], *config["target_models"]]):
        raise ValueError("Source or target is not supported by the verified asset registry")
    seeds = config["bsr_seeds"]
    if len(seeds) != 3 or len(set(seeds)) != 3:
        raise ValueError("Exactly three distinct BSR base seeds are required")
    for seed in [*seeds, config["bootstrap_seed"]]:
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**63 - 1000:
            raise ValueError("Invalid seed")
    batches = (config["sample_count"] + config["batch_size"] - 1) // config["batch_size"]
    for first, second in zip(sorted(seeds), sorted(seeds)[1:]):
        if second - first < batches:
            raise ValueError("BSR base-seed streams would overlap across batches")
    build_methods(config)  # Validate all AttackConfig instances now.
    return config


def build_methods(config):
    methods = []

    def add(name, method, steps, views, alpha, alpha_kind):
        attack = AttackConfig(name, method, steps, views, config["epsilon"], alpha,
                              decay=config["momentum_decay"], blocks=config["blocks"],
                              rotation_degrees=config["rotation_degrees"])
        methods.append({**asdict(attack), "gradient_budget": steps * views,
                        "alpha_kind": alpha_kind,
                        "seeds": config["bsr_seeds"][:] if method == "bsr" else [None]})

    add("mi10_reference", "mi", 10, 1, config["epsilon"] / 10, "reference_epsilon_over_10")
    for budget in config["gradient_budgets"]:
        add(f"mi_g{budget}", "mi", budget, 1, config["epsilon"] / budget, "epsilon_over_steps")
        for views in (2, 4):
            add(f"bsr_m{views}_g{budget}", "bsr", budget // views, views,
                config["epsilon"] / (budget // views), "epsilon_over_steps")
        add(f"mi_g{budget}_fixed_step", "mi", budget, 1,
            config["epsilon"] / config["fixed_step_denominator"], "fixed_epsilon_over_10")
    return methods


def attack_config(method):
    return AttackConfig(**{key: method[key] for key in (
        "name", "method", "steps", "views", "epsilon", "alpha", "decay", "blocks", "rotation_degrees"
    )})


def build_jobs(methods):
    return [{"job_id": method["name"] + (f"_seed{seed}" if seed is not None else "_deterministic"),
             "method": method["name"], "seed": seed}
            for method in methods for seed in method["seeds"]]


def selection_from_record(record, test_labels=None):
    final_ids, pilot_ids = record["final_ids"], record["pilot_ids"]
    for name, ids, count, limit in (("final_ids", final_ids, 1000, 10000),
                                    ("pilot_ids", pilot_ids, 200, 10000),
                                    ("development_ids", record["development_ids"], 50, 50000)):
        if len(ids) != count or len(set(ids)) != count:
            raise ValueError(f"{name} has wrong count or duplicate IDs")
        if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < limit for i in ids):
            raise ValueError(f"Invalid {name}")
    if not set(pilot_ids) <= set(final_ids):
        raise ValueError("Inherited pilot IDs are not a subset of final IDs")
    pilot_set = set(pilot_ids)
    masks = {
        "full1000": list(range(len(final_ids))),
        "pilot200": [i for i, image_id in enumerate(final_ids) if image_id in pilot_set],
        "new800": [i for i, image_id in enumerate(final_ids) if image_id not in pilot_set],
    }
    if test_labels is not None:
        labels = np.asarray(test_labels)
        expected = record.get("test_label_sha256")
        if expected and hashlib.sha256(np.asarray(labels, dtype=np.int64).tobytes()).hexdigest() != expected:
            raise ValueError("Dataset labels differ from inherited selection")
        for subset, positions in masks.items():
            counts = np.bincount(labels[np.asarray(final_ids)[positions]], minlength=10)
            if not np.array_equal(counts, np.full(10, len(positions) // 10)):
                raise ValueError(f"Inherited {subset} is not class balanced")
    return {**record, "new_ids": [final_ids[i] for i in masks["new800"]], "subsets": masks,
            "sample_count": 1000,
            "new800_definition": "Not included in the initial pilot attack-effect evaluation. Full-test clean target predictions were already checked; this is not never-accessed target data.",
            "selection_policy": "Original final_ids and their exact order reused; no resampling or target-based filtering"}


def load_selection(config, test):
    path = ROOT / config["selection_source"]
    if pilot.sha256(path) != config["selection_sha256"]:
        raise ValueError("Inherited selection file hash mismatch")
    selected = selection_from_record(json.loads(path.read_text(encoding="utf-8")), test.targets)
    selected["selection_source"] = config["selection_source"]
    selected["selection_source_sha256"] = config["selection_sha256"]
    return selected


def environment():
    return {"python": platform.python_version(), "platform": platform.platform(),
            "torch": torch.__version__, "torchvision": torchvision.__version__,
            "numpy": np.__version__, "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0), "threads": torch.get_num_threads()}


def assets_signature(assets):
    return canonical_hash({key: assets[key] for key in ("model_repository", "model_commit", "sources", "models", "dataset")})


def prepare_run(out, config, selection, assets, *, resume=False, source_root=ROOT, source_files=SOURCE_FILES, env=None):
    out = Path(out)
    hashes = {relative: pilot.sha256(source_root / relative) for relative in source_files}
    env = environment() if env is None else env
    if resume:
        provenance = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
        frozen = json.loads((out / "config.frozen.json").read_text(encoding="utf-8"))
        frozen_ids = json.loads((out / "selection.json").read_text(encoding="utf-8"))
        if canonical_hash(config) != canonical_hash(frozen) or canonical_hash(selection) != canonical_hash(frozen_ids):
            raise ValueError("Resume config or selection differs from frozen run")
        if pilot.sha256(out / "config.frozen.json") != provenance["config_sha256"] or pilot.sha256(out / "selection.json") != provenance["selection_sha256"]:
            raise ValueError("Frozen run file checksum mismatch")
        if hashes != provenance["source_sha256"]:
            raise ValueError("Resume code differs from frozen code")
        for relative, digest in hashes.items():
            if pilot.sha256(out / "source_snapshot" / relative) != digest:
                raise ValueError("Frozen source snapshot checksum mismatch")
        if assets_signature(assets) != provenance["asset_signature"]:
            raise ValueError("Resume model or dataset assets differ")
        for key in ("torch", "torchvision", "cuda_runtime", "gpu"):
            if env.get(key) != provenance["environment"].get(key):
                raise ValueError(f"Resume runtime differs for {key}")
        return provenance
    out.mkdir(parents=True, exist_ok=False)
    pilot.dump_json(out / "config.frozen.json", config)
    pilot.dump_json(out / "selection.json", selection)
    for relative in source_files:
        destination = out / "source_snapshot" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_root / relative, destination)
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source_root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        head = None
    provenance = {
        "schema_version": 2, "stage": "full", "frozen_at": pilot.timestamp(),
        "config_sha256": pilot.sha256(out / "config.frozen.json"),
        "selection_sha256": pilot.sha256(out / "selection.json"),
        "source_sha256": hashes, "git_head": head, "assets": assets,
        "asset_signature": assets_signature(assets), "environment": env,
        "target_access": "Pilot target effects and full-test clean predictions were already observed. In this new run all configurations are frozen and all source attacks complete before target-effect evaluation; no target-based selection.",
        "randomness": "CPU generators fix batch-shared BSR sampling; CUDA grid_sample backward may remain nondeterministic",
        "api_calls": 0,
    }
    pilot.dump_json(out / "provenance.json", provenance)
    (out / "cache").mkdir()
    return provenance


def validate_payload(payload, images, labels, ids, method):
    adversarial = payload["adversarial"]
    if not isinstance(adversarial, torch.Tensor) or adversarial.dtype != torch.float32 or adversarial.device.type != "cpu" or adversarial.shape != images.shape:
        raise ValueError("Invalid adversarial cache tensor")
    if payload["ids"] != ids or not torch.equal(payload["labels"], labels):
        raise ValueError("Adversarial cache labels or IDs mismatch")
    if not torch.isfinite(adversarial).all() or adversarial.min() < 0 or adversarial.max() > 1:
        raise ValueError("Invalid cached pixels")
    linf = (adversarial - images).abs().flatten(1).amax(1)
    if linf.max() > method["epsilon"] + 1e-6:
        raise ValueError("Cached perturbation exceeds epsilon")
    if not torch.allclose(linf, payload["linf"], atol=1e-7, rtol=0):
        raise ValueError("Cached perturbation norm mismatch")
    predictions = payload["source_predictions"]
    if not isinstance(predictions, torch.Tensor) or predictions.shape != labels.shape or predictions.dtype != torch.int64 or (predictions < 0).any() or (predictions > 9).any():
        raise ValueError("Invalid cached source predictions")


def cache_paths(out, job):
    stem = Path(out) / "cache" / job["job_id"]
    return Path(str(stem) + ".pt"), Path(str(stem) + ".generation.json"), Path(str(stem) + ".complete.json")


def load_cached_job(out, job, method, images, labels, ids):
    tensor_path, generation_path, marker_path = cache_paths(out, job)
    if not marker_path.exists():
        return None  # A partial job is regenerated, never treated as complete.
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker["job_spec_sha256"] != canonical_hash({"job": job, "method": method}):
        raise ValueError("Cached job specification differs")
    if pilot.sha256(tensor_path) != marker["cache_sha256"] or pilot.sha256(generation_path) != marker["generation_sha256"]:
        raise ValueError("Completed attack cache checksum mismatch")
    payload = torch.load(tensor_path, map_location="cpu", weights_only=True)
    validate_payload(payload, images, labels, ids, method)
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    if generation["gradient_evaluations_per_image"] != method["gradient_budget"] or generation["sample_view_gradient_evaluations"] != len(ids) * method["gradient_budget"]:
        raise ValueError("Cached gradient budget mismatch")
    return payload, generation


def save_cached_job(out, job, method, payload, generation):
    tensor_path, generation_path, marker_path = cache_paths(out, job)
    temporary = tensor_path.with_name(tensor_path.name + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(tensor_path)
    atomic_json(generation_path, generation)
    atomic_json(marker_path, {"job_spec_sha256": canonical_hash({"job": job, "method": method}),
                             "cache_sha256": pilot.sha256(tensor_path),
                             "generation_sha256": pilot.sha256(generation_path)})


def warmup(source, dev_images, dev_labels, config, device):
    legacy = {"batch_size": config["batch_size"], "attack_seed": config["bsr_seeds"][0], "epsilon": config["epsilon"],
              "methods": [{"name": "bsr10x4_g40", "method": "bsr", "steps": 10, "views": 4,
                           "alpha": config["epsilon"] / 10, "blocks": config["blocks"], "rotation_degrees": config["rotation_degrees"]}]}
    return pilot.warm_up(source, dev_images, dev_labels, device, legacy)


def seed_spread(metrics):
    values = [item["asr"] for item in metrics["per_seed"] if item["asr"] is not None]
    return {"asr_seed_min": min(values) if values else None, "asr_seed_max": max(values) if values else None,
            "asr_seed_std": float(np.std(values, ddof=1)) if len(values) > 1 else (0.0 if values else None)}


def run_experiment(out, config, selection, train, test, device):
    methods = build_methods(config)
    methods_by_name = {method["name"]: method for method in methods}
    jobs = build_jobs(methods)
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
    warming = warmup(source, dev_images, dev_labels, config, device)
    job_results = []
    for number, job in enumerate(jobs, start=1):
        method = methods_by_name[job["method"]]
        cached = load_cached_job(out, job, method, images, labels, ids)
        print(f"JOB {number}/{len(jobs)} {job['job_id']} {'cache verified' if cached else 'generating'}", flush=True)
        if cached is None:
            attack_settings = {**config, "attack_seed": job["seed"] if job["seed"] is not None else config["bsr_seeds"][0]}
            with redirect_stdout(io.StringIO()):
                adversarial, generation = pilot.run_batched(source, images, labels, attack_config(method), attack_settings, device, job["job_id"])
            source_predictions = pilot.predict(source, adversarial, config["batch_size"], device)
            payload = {"adversarial": adversarial, "ids": ids, "labels": labels,
                       "source_predictions": torch.from_numpy(source_predictions),
                       "linf": (adversarial - images).abs().flatten(1).amax(1)}
            validate_payload(payload, images, labels, ids, method)
            generation.update({"method": method["name"], "seed": job["seed"], "job_id": job["job_id"]})
            save_cached_job(out, job, method, payload, generation)
        else:
            payload, generation = cached
        job_results.append({**job, "cache_path": f"cache/{job['job_id']}.pt", "generation": generation})
        atomic_json(out / "progress.json", {"completed_jobs": number, "total_jobs": len(jobs),
                                            "last_job": job["job_id"], "updated_at": pilot.timestamp()})
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
    atomic_json(out / "target_evaluation_started.json", {"at": target_started_at,
                                                        "all_generation_jobs_completed": len(job_results)})
    target_results = {}
    summary = []
    seed_rows = []
    prediction_rows = []
    comparisons = []
    for target_name in config["target_models"]:
        print(f"TARGET {target_name}: all attacks already generated", flush=True)
        target = load_model(target_name, ROOT, device)
        target_full_clean = pilot.full_clean_accuracy(target, test, 128, device)
        if target_full_clean["accuracy"] < config["clean_accuracy_floor"]:
            raise RuntimeError(f"Target clean accuracy below floor: {target_name}")
        clean = pilot.predict(target, images, config["batch_size"], device)
        target_results[target_name] = {"full_test_clean": target_full_clean,
                                       "evaluation_started_at": pilot.timestamp()}
        method_predictions, method_source_predictions = {}, {}
        for method in methods:
            adversarial_predictions, source_predictions = [], []
            for job in (item for item in jobs if item["method"] == method["name"]):
                # Method has generation metadata now; cache specification was
                # frozen before that observational field was attached.
                cache_method = {key: value for key, value in method.items() if key != "generation"}
                payload, _ = load_cached_job(out, job, cache_method, images, labels, ids)
                predicted = pilot.predict(target, payload["adversarial"], config["batch_size"], device)
                adversarial_predictions.append(predicted)
                source_prediction = payload["source_predictions"].numpy()
                source_predictions.append(source_prediction)
                for position, image_id in enumerate(ids):
                    prediction_rows.append({
                        "target": target_name, "method": method["name"], "seed": job["seed"],
                        "test_id": image_id, "label": int(labels[position]),
                        "clean_prediction": int(clean[position]), "adversarial_prediction": int(predicted[position]),
                        "source_clean_prediction": int(source_clean[position]),
                        "source_adversarial_prediction": int(source_prediction[position]),
                        "gradient_budget": method["gradient_budget"], "linf": float(payload["linf"][position]),
                        "in_pilot200": image_id in set(selection["pilot_ids"]),
                    })
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
                       "alpha": method["alpha"], "alpha_kind": method["alpha_kind"],
                       **metrics, **seed_spread(metrics), "source_asr": source_metrics["asr"],
                       "mean_attack_seconds": method["generation"]["mean_attack_seconds"],
                       "timing_scope": "Full1000 generation cost per seed, reused across targets and subsets; not subset-specific timing"}
                summary.append(row)
                for position, per_seed in enumerate(metrics["per_seed"]):
                    seed_rows.append({**{key: row[key] for key in ("target", "subset", "method", "steps", "views", "gradient_budget", "alpha", "alpha_kind")},
                                      **per_seed, "source_asr": source_metrics["per_seed"][position]["asr"],
                                      "attack_seconds": method["generation"]["per_seed"][position]["attack_seconds"]})
            for budget in config["gradient_budgets"]:
                pairs = [(f"bsr_m{views}_g{budget}", f"mi_g{budget}{suffix}")
                         for views in (2, 4) for suffix in ("", "_fixed_step")]
                pairs.append((f"bsr_m4_g{budget}", f"bsr_m2_g{budget}"))
                for first, second in pairs:
                    result = paired_bootstrap(y, clean[index], method_predictions[first][:, index], method_predictions[second][:, index],
                                              seed=config["bootstrap_seed"], n_bootstrap=config["bootstrap_replicates"])
                    comparisons.append({"target": target_name, "subset": subset, "method_a": first,
                                        "method_b": second, "gradient_budget": budget, **result})
        del target
        torch.cuda.empty_cache()
    expected_gradients = len(ids) * sum(methods_by_name[item["method"]]["gradient_budget"] for item in jobs)
    actual_gradients = sum(item["generation"]["sample_view_gradient_evaluations"] for item in job_results)
    if actual_gradients != expected_gradients:
        raise RuntimeError("Full experiment actual gradient total differs from matrix")
    results = {
        "schema_version": 2, "stage": "full", "completed_at": pilot.timestamp(), "images": len(ids),
        "source": config["source_model"], "source_full_test_clean": source_full_clean,
        "targets": target_results, "target_evaluation_started_at": target_started_at,
        "subsets": {name: len(values) for name, values in selection["subsets"].items()},
        "methods": {method["name"]: method for method in methods}, "jobs": job_results,
        "summary": summary, "comparisons": comparisons, "warmup": warming,
        "total_sample_view_gradient_evaluations": actual_gradients, "api_calls": 0,
        "limitations": ["One pretrained source and two pretrained targets, not independent training repeats",
                        "Three BSR seed streams, deterministic MI evaluated once per configuration; seed means are not best-of-seeds",
                        "Full1000 includes previously evaluated pilot200; new800 excluded from initial attack-effect evaluation but full-test clean predictions had already been checked",
                        "Paired image bootstrap is conditional on supplied models and attack seeds, not a training or all-randomness interval",
                        "Batch-shared BSR transforms and CUDA rotation backward can limit bitwise reproducibility",
                        "Time is a single synchronized observation per generation job, not repeated benchmarking",
                        "Equal gradient evaluations do not imply equal FLOPs or wall time",
                        "No target-effect feedback used to change attack settings, budgets, seeds or model selection"],
    }
    pilot.write_csv(out / "summary.csv", [{key: value for key, value in row.items() if key != "per_seed"} for row in summary])
    pilot.write_csv(out / "per_seed.csv", seed_rows)
    pilot.write_csv(out / "predictions.csv", prediction_rows)
    pilot.write_csv(out / "comparisons.csv", [{
        **{key: value for key, value in row.items() if key != "ci95"},
        "ci95_lower": row["ci95"][0] if row["ci95"] is not None else None,
        "ci95_upper": row["ci95"][1] if row["ci95"] is not None else None,
    } for row in comparisons])
    atomic_json(out / "results.json", results)
    atomic_json(out / "completion.json", {"completed_at": results["completed_at"], "sha256": {
        filename: pilot.sha256(out / filename) for filename in ("results.json", "summary.csv", "per_seed.csv", "predictions.csv", "comparisons.csv", "inputs.pt")}})
    if (out / "failure.json").exists():
        history = out / "failure_history"
        history.mkdir(exist_ok=True)
        (out / "failure.json").replace(history / f"recovered_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.json")
    print(f"V1_FULL_COMPLETED {out} gradients={actual_gradients:,}", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/v1_full.json")
    location = parser.add_mutually_exclusive_group()
    location.add_argument("--output", type=Path)
    location.add_argument("--resume", type=Path)
    args = parser.parse_args()
    config = read_config(args.config.resolve())
    device = pilot.setup_runtime()
    assets = prepare_assets(ROOT, download=False)
    train = load_cifar(ROOT, train=True, download=False)
    test = load_cifar(ROOT, train=False, download=False)
    selection = load_selection(config, test)
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
    out = (args.resume or args.output or ROOT / "experiments" / f"v1_full_{stamp}").resolve()
    prepare_run(out, config, selection, assets, resume=args.resume is not None)
    if args.resume and (out / "completion.json").exists():
        completion = json.loads((out / "completion.json").read_text(encoding="utf-8"))
        for filename, expected in completion["sha256"].items():
            if pilot.sha256(out / filename) != expected:
                raise ValueError("Completed result checksum mismatch")
        # Validate all attack caches as well; a completed result is not proof
        # that an adversarial artifact still matches its recorded checksum.
        images, labels = pilot.load_tensors(test, selection["final_ids"])
        for method in build_methods(config):
            for job in build_jobs([method]):
                if load_cached_job(out, job, method, images, labels, selection["final_ids"]) is None:
                    raise ValueError("Completed run is missing a completed attack cache")
        print(f"V1_FULL_ALREADY_COMPLETED_AND_VERIFIED {out}", flush=True)
        return
    try:
        run_experiment(out, config, selection, train, test, device)
    except Exception as error:
        atomic_json(out / "failure.json", {"failed_at": pilot.timestamp(), "type": type(error).__name__, "message": str(error)})
        raise


if __name__ == "__main__":
    main()
