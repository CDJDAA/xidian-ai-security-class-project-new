"""Re-render recorded V1 budget/time figures without changing frozen code.

This presentation-only pass moves the shared legend outside both panels and
uses an explanatory caption instead of overlapping point annotations. It reads
exported results, makes no model calls, and updates the report artifact hashes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SERIES = (
    ("MI-FGSM, alpha=eps/T", "mi_g{}", "#245b93", "o", "-"),
    ("BSR, M=2 (three-seed mean)", "bsr_m2_g{}", "#d87822", "s", "-"),
    ("BSR, M=4 (three-seed mean)", "bsr_m4_g{}", "#21845b", "^", "-"),
    ("MI-FGSM, alpha=eps/10", "mi_g{}_fixed_step", "#6f637e", "D", "--"),
)
BUDGETS = (20, 40, 80)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target_label(name):
    return {"cifar10_mobilenetv2_x1_0": "MobileNetV2", "cifar10_vgg11_bn": "VGG11-BN"}.get(name, name)


def value(number):
    return np.nan if number is None else float(number)


def render(results, destination, subset, by_time):
    indexed = {(row["target"], row["subset"], row["method"]): row for row in results["summary"]}
    targets = list(results["targets"])
    if len(targets) != 2:
        raise ValueError("Expected the two frozen V1 targets")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, target in zip(axes, targets):
        for label, pattern, color, marker, style in SERIES:
            rows = [indexed[(target, subset, pattern.format(budget))] for budget in BUDGETS]
            xs = [row["mean_attack_seconds"] for row in rows] if by_time else BUDGETS
            ys = [100 * value(row["asr"]) for row in rows]
            ax.plot(xs, ys, label=label, color=color, marker=marker, linestyle=style, linewidth=1.7, markersize=5)
            if rows[0]["attack_seed_count"] > 1:
                lows = [100 * value(row["asr_seed_min"]) for row in rows]
                highs = [100 * value(row["asr_seed_max"]) for row in rows]
                ax.fill_between(xs, lows, highs, color=color, alpha=0.14)
        ax.set_title(target_label(target), fontsize=11)
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.22)
        ax.set_xlabel("Mean generation time per 1,000 images (s)" if by_time else "Gradient evaluations per image, G = T x M", fontsize=9)
        if not by_time:
            ax.set_xticks(BUDGETS)
    axes[0].set_ylabel("Transfer attack success rate (%)", fontsize=10)
    fig.suptitle(f"CIFAR-10 pretrained targets | {subset} | source: ResNet-20", y=0.98, fontsize=11)
    fig.text(0.5, 0.925, "BSR shading: range across three attack seeds, not a confidence interval", ha="center", fontsize=8)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.065), ncol=2, frameon=False, fontsize=9)
    caption = "Points along each curve use G=20, 40, 80. BSR time is the mean cost of three separate seeded runs."
    if not by_time:
        caption = "Untargeted Linf eps=8/255; CIFAR-adapted BSR (two blocks/axis, +/-10 deg); mean ASR, not best-of-seeds."
    fig.text(0.5, 0.025, caption, ha="center", fontsize=7.8)
    fig.text(0.5, 0.001, "Time is one observed execution per job, not a timing CI; new800 evaluation reuses full1000 generation cost.", ha="center", fontsize=7.5)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.83, bottom=0.29, wspace=0.08)
    stem = ("asr_vs_time_" if by_time else "asr_vs_budget_") + subset
    fig.savefig(destination / f"{stem}.png", dpi=180, bbox_inches="tight")
    fig.savefig(destination / f"{stem}.svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    return [f"{stem}.png", f"{stem}.svg"]


def render_report(report):
    report = Path(report).resolve()
    verification_path = report / "verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    result_path = report / "results.json"
    if sha256(result_path) != verification["artifacts_sha256"]["results.json"]:
        raise ValueError("Recorded results hash mismatch; refusing presentation-only re-render")
    results = json.loads(result_path.read_text(encoding="utf-8"))
    if results.get("schema_version") != 2 or results.get("stage") != "full":
        raise ValueError("Expected completed V1 full results")
    matplotlib.rcParams["svg.hashsalt"] = "course-v1-full-presentation"
    rendered = []
    for subset in ("full1000", "new800"):
        for by_time in (False, True):
            rendered.extend(render(results, report, subset, by_time))
    for filename in rendered:
        verification["artifacts_sha256"][filename] = sha256(report / filename)
    verification["figure_post_render"] = {
        "renderer": "course_tools/render_v1_full_figures.py",
        "renderer_sha256": sha256(__file__),
        "rendered_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": rendered,
        "scope": "Legend and label placement only; recorded metrics/predictions/frozen experiment code unchanged",
        "model_calls": 0,
    }
    verification_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report), "updated_figures": rendered, "recorded_results_sha256": sha256(result_path)}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    render_report(args.report)


if __name__ == "__main__":
    main()
