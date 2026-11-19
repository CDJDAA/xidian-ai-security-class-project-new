"""Fixed, reviewed CIFAR budget benchmark; no LLM or model-service calls.

Run from the project root with: python -m course_tools.run_v1 --help
Raw runs live in ignored experiments/. Export selected evidence separately.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torchvision
from torchvision.utils import make_grid, save_image

from course_tools.v1_assets import load_cifar, load_model, prepare_assets
from course_tools.v1_attacks import AttackConfig, bsr_transform, run_attack
from course_tools.v1_metrics import paired_bootstrap, summarise_predictions

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "course_tools/run_v1.py", "course_tools/v1_assets.py",
    "course_tools/v1_attacks.py", "course_tools/v1_metrics.py",
    "course_tools/report_v1.py",
    "docs/research/v1-budget-protocol.md",
)


def timestamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def dump_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config["schema_version"] != 1 or config["dataset"] != "CIFAR10":
        raise ValueError("Unsupported benchmark schema or dataset")
    for key in ("batch_size", "pilot_per_class", "final_per_class", "development_per_class", "bootstrap_replicates"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("split_seed", "attack_seed", "bootstrap_seed"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63:
            raise ValueError(f"{key} must be an integer in [0, 2**63)")
    if not 0 < config["epsilon"] <= 1 or not 0 < config["clean_accuracy_floor"] <= 1:
        raise ValueError("Invalid epsilon or clean-accuracy floor")
    if not 0 < config["pilot_per_class"] <= config["final_per_class"] <= 1000:
        raise ValueError("Invalid pilot/final sample counts")
    names = [item["name"] for item in config["methods"]]
    required = {"mi10_g10", "mi40_g40", "bsr10x4_g40", "mi40_g40_large_step"}
    if len(names) != len(set(names)) or any(not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in names):
        raise ValueError("Method names must be unique safe identifiers")
    if required != set(names):
        raise ValueError("This pilot runner requires all four named comparison methods, and no others")
    attack_configs(config)  # Validate every attack before loading data/models.
    return config


def attack_configs(config):
    return [AttackConfig(epsilon=config["epsilon"], **item) for item in config["methods"]]


def stratified_ids(labels, per_class, seed):
    labels = np.asarray(labels)
    rng = np.random.default_rng(seed)
    selected = []
    for label in range(10):
        candidates = np.flatnonzero(labels == label)
        if len(candidates) < per_class:
            raise ValueError("Not enough images for stratified selection")
        selected.extend(rng.permutation(candidates)[:per_class].tolist())
    return rng.permutation(selected).tolist()


def selection_manifest(train, test, config):
    # Select the final set first; pick a class-balanced pilot without predictions.
    final_ids = stratified_ids(test.targets, config["final_per_class"], config["split_seed"])
    pilot_ids = []
    for label in range(10):
        class_ids = [index for index in final_ids if test.targets[index] == label]
        pilot_ids.extend(class_ids[:config["pilot_per_class"]])
    pilot_ids = np.random.default_rng(config["split_seed"] + 1).permutation(pilot_ids).tolist()
    return {
        "split_seed": config["split_seed"],
        "development_split": "train (public weights may have seen these images)",
        "development_ids": stratified_ids(train.targets, config["development_per_class"], config["split_seed"]),
        "pilot_split": "test",
        "pilot_ids": pilot_ids,
        "final_ids": final_ids,
        "pilot_is_subset_of_final": True,
        "order": "Fixed shuffle after stratification; batch-shared transforms are not tied to a single class",
        "test_label_sha256": hashlib.sha256(np.asarray(test.targets, dtype=np.int64).tobytes()).hexdigest(),
        "rule": "All IDs selected from labels without model predictions; pilot not used for hyperparameter tuning",
    }


def load_tensors(dataset, ids):
    pairs = [dataset[index] for index in ids]
    return torch.stack([p[0] for p in pairs]), torch.tensor([p[1] for p in pairs], dtype=torch.long)


def setup_runtime():
    if not torch.cuda.is_available():
        raise RuntimeError("This benchmark run requires the verified CUDA environment")
    torch.set_num_threads(4)
    torch.manual_seed(42)
    np.random.seed(42)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    # CUDA grid_sample backward has no deterministic implementation. Record the
    # limitation rather than claiming bitwise repeatability from sampling seeds.
    return torch.device("cuda")


@torch.inference_mode()
def predict(model, inputs, batch_size, device):
    predictions = []
    for start in range(0, len(inputs), batch_size):
        logits = model(inputs[start:start + batch_size].to(device))
        if not torch.isfinite(logits).all():
            raise RuntimeError("Nonfinite classifier logits")
        predictions.append(logits.argmax(1).cpu())
    return torch.cat(predictions).numpy()


@torch.inference_mode()
def full_clean_accuracy(model, dataset, batch_size, device):
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    correct = 0
    count = 0
    start = time.perf_counter()
    for images, labels in loader:
        logits = model(images.to(device))
        if not torch.isfinite(logits).all():
            raise RuntimeError("Nonfinite clean logits")
        correct += (logits.argmax(1).cpu() == labels).sum().item()
        count += len(labels)
    torch.cuda.synchronize()
    return {"correct": correct, "count": count, "accuracy": correct / count,
            "seconds": time.perf_counter() - start}


def warm_up(model, inputs, labels, device, config):
    batch_size = min(config["batch_size"], len(inputs))
    for _ in range(2):
        image = inputs[:batch_size].to(device).clone().requires_grad_(True)
        loss = torch.nn.functional.cross_entropy(model(image), labels[:len(image)].to(device))
        torch.autograd.grad(loss, image)
    bsr = next(cfg for cfg in attack_configs(config) if cfg.name == "bsr10x4_g40")
    warm_config = AttackConfig("warmup_bsr", "bsr", 1, bsr.views, bsr.epsilon, bsr.alpha,
                               blocks=bsr.blocks, rotation_degrees=bsr.rotation_degrees)
    _, bsr_stats = run_attack(model, inputs[:batch_size].to(device), labels[:batch_size].to(device),
                              warm_config, config["attack_seed"])
    torch.cuda.synchronize()
    return {"original_view_batches": 2, "bsr_batches": 1, "images_per_batch": batch_size,
            "sample_view_gradient_evaluations": 2 * batch_size + bsr_stats["sample_view_gradient_evaluations"],
            "included_in_attack_budget": False}


def freeze_run(out, config_path, config, ids, assets, stage):
    out.mkdir(parents=True, exist_ok=False)
    dump_json(out / "config.frozen.json", config)
    dump_json(out / "selection.json", ids)
    snapshot = out / "source_snapshot"
    snapshot.mkdir()
    hashes = {}
    for relative in SOURCE_FILES:
        source = ROOT / relative
        hashes[relative] = sha256(source)
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    try:
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        git_status = subprocess.check_output(["git", "status", "--short", "--", "."], cwd=ROOT, text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        git_head, git_status = None, []
    manifest = {
        "schema_version": 1, "stage": stage, "frozen_at": timestamp(),
        "config_source": str(config_path.relative_to(ROOT)) if config_path.is_relative_to(ROOT) else config_path.name,
        "config_sha256": sha256(out / "config.frozen.json"),
        "selection_sha256": sha256(out / "selection.json"),
        "source_sha256": hashes, "git_head": git_head, "git_working_changes": git_status,
        "assets": assets,
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "torch": torch.__version__, "torchvision": torchvision.__version__,
                        "numpy": np.__version__, "cuda_runtime": torch.version.cuda,
                        "gpu": torch.cuda.get_device_name(0), "threads": torch.get_num_threads()},
        "target_access": "Within this process, no target test inference before freeze; generation uses surrogate only; pilot target loaded after all attacks. Prior runs and train-only clean asset checks must be recorded separately.",
        "reproducibility_limit": "CPU generator controls BSR sampling; CUDA grid_sample backward may be nondeterministic",
        "api_calls": 0,
    }
    dump_json(out / "provenance.json", manifest)
    return manifest


def run_batched(model, images, labels, cfg, config, device, progress_label):
    adversarial = []
    counts = {"sample_view_gradient_evaluations": 0, "backward_calls": 0}
    batch_seeds = []
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start_time = time.perf_counter()
    batch_size = config["batch_size"]
    for batch_number, start in enumerate(range(0, len(images), batch_size)):
        seed = config["attack_seed"] + batch_number
        adv, stats = run_attack(
            model, images[start:start + batch_size].to(device),
            labels[start:start + batch_size].to(device), cfg, seed,
        )
        torch.cuda.synchronize()
        adversarial.append(adv.cpu())
        for key in counts:
            counts[key] += int(stats[key])
        if int(stats["gradient_evaluations_per_image"]) != cfg.steps * cfg.views:
            raise RuntimeError("Actual gradient budget differs from declared budget")
        batch_seeds.append(seed)
        print(f"{progress_label}: {min(start+batch_size, len(images))}/{len(images)} images", flush=True)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start_time
    joined = torch.cat(adversarial)
    linf = (joined - images).abs().flatten(1).amax(1)
    if not torch.isfinite(joined).all() or joined.min() < 0 or joined.max() > 1:
        raise RuntimeError("Invalid adversarial pixels")
    if float(linf.max()) > cfg.epsilon + 1e-6:
        raise RuntimeError("Attack exceeds pixel perturbation budget")
    expected = len(images) * cfg.steps * cfg.views
    if counts["sample_view_gradient_evaluations"] != expected:
        raise RuntimeError("Total actual sample-view gradient budget mismatch")
    return joined, {
        **counts, "gradient_evaluations_per_image": cfg.steps * cfg.views,
        "attack_seconds": elapsed, "images_per_second": len(images) / elapsed,
        "peak_cuda_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
        "peak_cuda_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
        "linf_max": float(linf.max()), "linf_mean": float(linf.mean()),
        "all_constraints_passed": True, "batch_seeds": batch_seeds,
        "timing_scope": "GPU-synchronized attack loop including transforms and result CPU transfer; excludes warmup, source/target evaluation",
    }


def development_run(out, config, ids, train, device):
    images, labels = load_tensors(train, ids["development_ids"])
    source = load_model(config["source_model"], ROOT, device)
    clean = predict(source, images, config["batch_size"], device)
    transformed_acc = []
    bsr = next(cfg for cfg in attack_configs(config) if cfg.name == "bsr10x4_g40")
    generator = torch.Generator().manual_seed(config["attack_seed"])
    for _ in range(4):
        transformed = bsr_transform(images, generator, blocks=bsr.blocks, rotation_degrees=bsr.rotation_degrees)
        transformed_acc.append(float((predict(source, transformed, config["batch_size"], device) == labels.numpy()).mean()))
    n = min(8, len(images))
    transformed = bsr_transform(images[:n], generator, blocks=bsr.blocks, rotation_degrees=bsr.rotation_degrees)
    save_image(make_grid(torch.cat([images[:n], transformed]), nrow=n), out / "development_transforms.png")
    warmup = warm_up(source, images, labels, device, config)
    timings = {}
    for cfg in attack_configs(config):
        _, stats = run_batched(source, images[:n], labels[:n], cfg, config, device, cfg.name)
        timings[cfg.name] = stats
    result = {
        "stage": "development_only", "completed_at": timestamp(), "images": len(images),
        "source_clean_accuracy": float((clean == labels.numpy()).mean()),
        "source_transformed_clean_accuracies": transformed_acc,
        "profile_images_per_method": n, "profiles": timings, "warmup": warmup,
        "target_access": "none", "api_calls": 0,
        "interpretation": "Implementation and timing diagnostic on train development subset; no transfer claims",
    }
    dump_json(out / "development.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(out, rows, images, adversarial, labels, config):
    names = [row["method"] for row in rows]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    axes[0].bar(names, [100 * row["asr"] if row["asr"] is not None else np.nan for row in rows])
    axes[0].set_ylabel("Target transfer ASR (%)")
    axes[0].set_ylim(0, 100)
    axes[1].bar(names, [row["attack_seconds"] for row in rows])
    axes[1].set_ylabel("Attack generation time (seconds)")
    for ax in axes:
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.grid(axis="y", alpha=0.2)
    figure.suptitle(f"CIFAR-10: {config['source_model']} to {config['target_model']}\n{len(images)} fixed pilot images")
    figure.tight_layout()
    figure.savefig(out / "comparison.png", dpi=160)
    plt.close(figure)
    n = min(8, len(images))
    figure, axes = plt.subplots(3, n, figsize=(n * 1.6, 5.2), squeeze=False)
    for index in range(n):
        axes[0, index].imshow(images[index].permute(1, 2, 0).numpy())
        axes[0, index].set_title(f"label={int(labels[index])}")
        for row_index, method in enumerate(("mi40_g40", "bsr10x4_g40"), start=1):
            axes[row_index, index].imshow(adversarial[method][index].permute(1, 2, 0).numpy())
        for row_index in range(3):
            axes[row_index, index].set_xticks([])
            axes[row_index, index].set_yticks([])
    for row_index, label in enumerate(("Clean", "MI-40", "BSR-10x4")):
        axes[row_index, 0].set_ylabel(label)
    figure.suptitle("First fixed examples; not selected by attack success")
    figure.tight_layout()
    figure.savefig(out / "examples.png", dpi=160)
    plt.close(figure)


def pilot_run(out, config, ids, train, test, device):
    images, labels = load_tensors(test, ids["pilot_ids"])
    dev_images, dev_labels = load_tensors(train, ids["development_ids"])
    source = load_model(config["source_model"], ROOT, device)
    source_full_clean = full_clean_accuracy(source, test, 128, device)
    if source_full_clean["accuracy"] < config["clean_accuracy_floor"]:
        raise RuntimeError("Source clean accuracy below declared floor; check weights and preprocessing")
    source_clean = predict(source, images, config["batch_size"], device)
    warmup = warm_up(source, dev_images, dev_labels, device, config)
    attacks = {}
    attack_stats = {}
    source_adv = {}
    for cfg in attack_configs(config):
        adversarial, stats = run_batched(source, images, labels, cfg, config, device, cfg.name)
        attacks[cfg.name] = adversarial
        attack_stats[cfg.name] = stats
        source_adv[cfg.name] = predict(source, adversarial, config["batch_size"], device)
        torch.save({"adversarial": adversarial, "ids": ids["pilot_ids"], "labels": labels}, out / f"{cfg.name}.pt")
        dump_json(out / f"{cfg.name}.generation.json", stats)
    # All candidate attacks are complete before any target evaluation here.
    target_started_at = timestamp()
    target = load_model(config["target_model"], ROOT, device)
    target_full_clean = full_clean_accuracy(target, test, 128, device)
    if target_full_clean["accuracy"] < config["clean_accuracy_floor"]:
        raise RuntimeError("Target clean accuracy below declared floor; check weights and preprocessing")
    target_clean = predict(target, images, config["batch_size"], device)
    target_adv = {}
    summary_rows = []
    prediction_rows = []
    method_results = {}
    for cfg in attack_configs(config):
        prediction = predict(target, attacks[cfg.name], config["batch_size"], device)
        target_adv[cfg.name] = prediction
        target_metrics = summarise_predictions(labels.numpy(), target_clean, prediction)
        source_metrics = summarise_predictions(labels.numpy(), source_clean, source_adv[cfg.name])
        method_results[cfg.name] = {"target": target_metrics, "source": source_metrics, "generation": attack_stats[cfg.name]}
        summary_rows.append({"method": cfg.name, "steps": cfg.steps, "views": cfg.views,
                             "gradient_budget": cfg.steps * cfg.views, "alpha": cfg.alpha,
                             **{key: target_metrics[key] for key in ("clean_accuracy", "robust_accuracy", "asr_numerator", "asr_denominator", "asr")},
                             "source_asr": source_metrics["asr"],
                             "attack_seconds": attack_stats[cfg.name]["attack_seconds"],
                             "peak_cuda_allocated_mib": attack_stats[cfg.name]["peak_cuda_allocated_mib"]})
        linf = (attacks[cfg.name] - images).abs().flatten(1).amax(1)
        for position, image_id in enumerate(ids["pilot_ids"]):
            prediction_rows.append({
                "method": cfg.name, "test_id": image_id, "label": int(labels[position]),
                "source_clean_prediction": int(source_clean[position]),
                "source_adversarial_prediction": int(source_adv[cfg.name][position]),
                "target_clean_prediction": int(target_clean[position]),
                "target_adversarial_prediction": int(prediction[position]),
                "target_clean_correct": int(target_clean[position] == int(labels[position])),
                "target_attack_success": int(target_clean[position] == int(labels[position]) and prediction[position] != int(labels[position])),
                "gradient_budget": cfg.steps * cfg.views, "linf": float(linf[position]),
                "batch_seed": config["attack_seed"] + position // config["batch_size"],
            })
    comparisons = {}
    for baseline in ("mi10_g10", "mi40_g40", "mi40_g40_large_step"):
        comparisons[f"bsr_minus_{baseline}"] = paired_bootstrap(
            labels.numpy(), target_clean, target_adv["bsr10x4_g40"], target_adv[baseline],
            seed=config["bootstrap_seed"], n_bootstrap=config["bootstrap_replicates"],
        )
    results = {
        "schema_version": 1, "stage": "pilot", "completed_at": timestamp(),
        "images": len(images), "source": config["source_model"], "target": config["target_model"],
        "source_full_test_clean": source_full_clean, "target_full_test_clean": target_full_clean,
        "target_evaluation_started_at": target_started_at, "methods": method_results,
        "paired_comparisons": comparisons, "warmup": warmup,
        "total_sample_view_gradient_evaluations": sum(s["sample_view_gradient_evaluations"] for s in attack_stats.values()),
        "limitations": ["200-image single-seed pilot; not a conclusive benchmark",
                        "One source/target pair and CIFAR-adapted BSR settings",
                        "Equal gradient evaluations do not imply equal FLOPs or time",
                        "CUDA transform backward may be nondeterministic; seed controls sampling",
                        "No target feedback used to generate attacks or select hyperparameters"],
        "api_calls": 0,
    }
    dump_json(out / "results.json", results)
    write_csv(out / "summary.csv", summary_rows)
    write_csv(out / "predictions.csv", prediction_rows)
    plot_results(out, summary_rows, images, attacks, labels, config)
    print(json.dumps({"output": str(out), "summary": summary_rows, "paired": comparisons}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("develop", "pilot"), required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/v1_budget.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config_path = args.config.resolve()
    config = read_config(config_path)
    device = setup_runtime()
    assets = prepare_assets(ROOT, download=False)
    train = load_cifar(ROOT, train=True, download=False)
    test = load_cifar(ROOT, train=False, download=False)
    ids = selection_manifest(train, test, config)
    stamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
    out = args.output.resolve() if args.output else ROOT / "experiments" / f"v1_{args.stage}_{stamp}"
    freeze_run(out, config_path, config, ids, assets, args.stage)
    try:
        if args.stage == "develop":
            development_run(out, config, ids, train, device)
        else:
            pilot_run(out, config, ids, train, test, device)
    except Exception as error:
        dump_json(out / "failure.json", {"failed_at": timestamp(), "type": type(error).__name__, "message": str(error)})
        raise
    print(f"V1_COMPLETED {out}", flush=True)


if __name__ == "__main__":
    main()
