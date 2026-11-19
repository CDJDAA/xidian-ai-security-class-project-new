"""Chinese scientific figures from a completed V1 sweep; never runs models.

The original CSVs remain untouched. Optional extra paired comparisons contain
M2-minus-M4 and fixed-MI-minus-epsilon/T-MI image-bootstrap differences.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np


TARGETS = ("cifar10_mobilenetv2_x1_0", "cifar10_vgg11_bn")
TARGET_LABELS = {TARGETS[0]: "MobileNetV2", TARGETS[1]: "VGG11-BN"}
METHODS = (
    ("mi_g{}_fixed_step", "MI：固定步长 ε/10", "#365D8D", "o", "-"),
    ("mi_g{}", "MI：按步数缩放 ε/T", "#8E6B98", "D", "--"),
    ("bsr_m2_g{}", "BSR：双视图（3 种子均值）", "#D77728", "s", "-"),
    ("bsr_m4_g{}", "BSR：四视图（3 种子均值）", "#268474", "^", "-"),
)
PAIRS = (
    (2, True, "双视图 BSR − 固定步长 MI", "#D77728", "s", "-"),
    (2, False, "双视图 BSR − 按步数缩放 MI", "#D77728", "o", "--"),
    (4, True, "四视图 BSR − 固定步长 MI", "#268474", "^", "-"),
    (4, False, "四视图 BSR − 按步数缩放 MI", "#268474", "D", "--"),
)
INPUTS = ("summary.csv", "per_seed.csv", "comparisons.csv", "predictions.csv",
          "config.frozen.json", "results.json", "selection.json", "completion.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def configure_font():
    candidates = [Path("C:/Windows/Fonts/msyh.ttc"), Path("/mnt/c/Windows/Fonts/msyh.ttc")]
    for candidate in candidates:
        if candidate.exists():
            font_manager.fontManager.addfont(str(candidate))
            bold = candidate.with_name("msyhbd.ttc")
            if bold.exists():
                font_manager.fontManager.addfont(str(bold))
            name = font_manager.FontProperties(fname=str(candidate)).get_name()
            break
    else:
        name = "DejaVu Sans"
        for font in font_manager.fontManager.ttflist:
            if font.name in ("Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Micro Hei"):
                name = font.name
                break
        if name == "DejaVu Sans":
            raise RuntimeError("A Chinese font is required to render the annotated figures")
    plt.rcParams.update({
        "font.family": name, "font.size": 10.5, "axes.titlesize": 12,
        "axes.labelsize": 11, "xtick.labelsize": 9.5, "ytick.labelsize": 10,
        "axes.unicode_minus": False, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white",
        "savefig.facecolor": "white", "svg.fonttype": "path",
        "axes.axisbelow": True,
    })
    return name


def make_index(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        if key in result:
            raise ValueError(f"Duplicate figure input row: {key}")
        result[key] = row
    return result


def setup_axis(axis, budgets, ylabel, *, zero=False, limit=None):
    axis.set_xticks(budgets)
    axis.set_xlabel("每图梯度预算 G")
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", color="#D8DEE6", linewidth=0.7, alpha=0.85)
    axis.grid(axis="x", color="#E9EDF2", linewidth=0.5, alpha=0.6)
    if zero:
        axis.axhline(0, color="#505C68", linestyle=":", linewidth=1.3, zorder=2)
    if limit is not None:
        axis.set_xlim(*limit)


def paired_arrays(rows):
    delta = np.array([float(row["difference_a_minus_b"]) * 100 for row in rows])
    lower = np.array([float(row["ci95_lower"]) * 100 for row in rows])
    upper = np.array([float(row["ci95_upper"]) * 100 for row in rows])
    if (lower > upper).any() or not np.isfinite(np.concatenate((delta, lower, upper))).all():
        raise ValueError("Invalid paired interval in figure inputs")
    return delta, lower, upper


def draw_pair(axis, budgets, rows, label, color, marker, linestyle, *, ribbon=False):
    delta, lower, upper = paired_arrays(rows)
    axis.plot(budgets, delta, marker=marker, color=color, linestyle=linestyle,
              linewidth=1.8, markersize=5.2, label=label, zorder=4)
    if ribbon:
        axis.fill_between(budgets, lower, upper, color=color, alpha=0.09, linewidth=0)
    # Draw exact bounds rather than deriving symmetric error bars. All x
    # positions retain their actual gradient budgets; no horizontal jitter.
    axis.vlines(budgets, lower, upper, color=color, alpha=0.48, linewidth=0.95, zorder=3)
    cap = 0.26 if max(budgets) - min(budgets) < 25 else 0.45
    axis.hlines(lower, np.array(budgets) - cap, np.array(budgets) + cap,
                color=color, alpha=0.48, linewidth=0.95)
    axis.hlines(upper, np.array(budgets) - cap, np.array(budgets) + cap,
                color=color, alpha=0.48, linewidth=0.95)


def get_pair(comparisons, target, subset, budgets, views, fixed):
    suffix = "_fixed_step" if fixed else ""
    return [comparisons[(target, subset, f"bsr_m{views}_g{budget}", f"mi_g{budget}{suffix}")]
            for budget in budgets]


def finish(fig, axes, output, stem, title, note, *, legend=True, legend_columns=2,
           bottom=0.24, top=0.86):
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)
    if legend:
        axis = np.asarray(axes, dtype=object).ravel()[0]
        handles, labels = axis.get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.075),
                   frameon=False, ncol=legend_columns, fontsize=10, handlelength=2.8,
                   columnspacing=2.2)
    fig.text(0.5, 0.018, note, ha="center", va="bottom", fontsize=9.1, color="#4C5968")
    fig.subplots_adjust(left=0.065, right=0.98, bottom=bottom, top=top,
                        wspace=0.25, hspace=0.48)
    for extension in ("png", "svg"):
        fig.savefig(output / f"{stem}.{extension}", dpi=300)
    plt.close(fig)


def plot_asr(summary, budgets, output):
    fig, axes = plt.subplots(1, 2, figsize=(14.4, 5.7))
    for axis, target in zip(axes, TARGETS):
        for template, label, color, marker, linestyle in METHODS:
            rows = [summary[(target, "full1000", template.format(g))] for g in budgets]
            values = [float(row["asr"]) * 100 for row in rows]
            axis.plot(budgets, values, marker=marker, color=color, linestyle=linestyle,
                      linewidth=1.9, markersize=5.3, label=label, zorder=3)
            if template.startswith("bsr"):
                axis.fill_between(budgets, [float(row["asr_seed_min"]) * 100 for row in rows],
                                  [float(row["asr_seed_max"]) * 100 for row in rows],
                                  color=color, alpha=0.14, linewidth=0)
        count = summary[(target, "full1000", METHODS[0][0].format(budgets[0]))]["asr_denominator"]
        axis.set_title(f"{TARGET_LABELS[target]}｜ASR 分母 {count} 张")
        setup_axis(axis, budgets, "条件迁移攻击成功率 ASR（%）")
        axis.set_ylim(0, 100)
    finish(fig, axes, output, "01_asr_full1000", "相同梯度预算下，四种配置的迁移成功率",
           "全 1,000 张；BSR 阴影为三个种子的最小—最大范围，不是置信区间。点间连线仅辅助阅读。")


def plot_gains(comparisons, budgets, output, *, zoom=False):
    selected = [g for g in budgets if 20 <= g <= 40] if zoom else budgets
    fig, axes = plt.subplots(1, 2, figsize=(14.4, 6.0))
    for axis, target in zip(axes, TARGETS):
        for views, fixed, label, color, marker, linestyle in PAIRS:
            rows = get_pair(comparisons, target, "full1000", selected, views, fixed)
            draw_pair(axis, selected, rows, label, color, marker, linestyle)
        axis.set_title(TARGET_LABELS[target])
        setup_axis(axis, selected, "ASR 差值：BSR − MI（百分点）", zero=True,
                   limit=(min(selected) - 1.1, max(selected) + 1.1) if zoom else None)
    finish(fig, axes, output, "03_gain_detail_20_40" if zoom else "02_gain_full1000",
           "G=20–40：均值翻转附近的差值与区间" if zoom else "BSR 相对两套 MI 步长的收益与区间",
           "全 1,000 张；误差条为原图片配对 95% 区间，未经多重比较校正；零轴表示均值相同。\n"
           "区间条件于当前模型和三个已有种子；连线的过零位置不是交叉点的置信区间。",
           bottom=0.27, top=0.86)


def plot_extra(comparisons, budgets, output):
    fig, axes = plt.subplots(1, 2, figsize=(14.4, 5.9))
    extra_specs = (
        ("bsr_m2_g{}", "bsr_m4_g{}", "双视图 BSR − 四视图 BSR", "#A05B22", "s", "-"),
        ("mi_g{}_fixed_step", "mi_g{}", "固定步长 MI − 按步数缩放 MI", "#5D629B", "D", "--"),
    )
    for axis, target in zip(axes, TARGETS):
        for a, b, label, color, marker, style in extra_specs:
            rows = [comparisons[(target, "full1000", a.format(g), b.format(g))] for g in budgets]
            draw_pair(axis, budgets, rows, label, color, marker, style)
        axis.set_title(TARGET_LABELS[target])
        setup_axis(axis, budgets, "ASR 配对差（百分点）", zero=True)
    finish(fig, axes, output, "04_view_and_step_rule_contrasts", "视图数量与 MI 步长规则：两个直接配对对照",
           "全 1,000 张；基于已有逐图预测补算，误差条为图片配对 95% 区间，未经多重比较校正。\n"
           "正值分别表示双视图 BSR 更高、固定步长 MI 更高；两条曲线的比较对象不同。",
           bottom=0.27, top=0.86)


def plot_seeds(summary, seeds, budgets, output):
    fig, axes = plt.subplots(2, 2, figsize=(14.4, 9.4))
    colors = {42: "#4C78A8", 142: "#DC8C36", 242: "#6A9B70"}
    for row_index, target in enumerate(TARGETS):
        for column_index, views in enumerate((2, 4)):
            axis = axes[row_index, column_index]
            for seed, color in colors.items():
                rows = [seeds[(target, "full1000", f"bsr_m{views}_g{g}", str(seed))] for g in budgets]
                axis.plot(budgets, [float(row["asr"]) * 100 for row in rows],
                          marker="o", color=color, linewidth=1.6, markersize=4.5, label=f"BSR 种子 {seed}")
            baseline = [summary[(target, "full1000", f"mi_g{g}_fixed_step")] for g in budgets]
            axis.plot(budgets, [float(row["asr"]) * 100 for row in baseline],
                      color="#5C6672", linestyle="--", linewidth=1.5, label="固定步长 MI（单次）")
            axis.set_title(f"{TARGET_LABELS[target]}｜BSR {'双' if views == 2 else '四'}视图")
            setup_axis(axis, budgets, "条件迁移 ASR（%）")
    finish(fig, axes, output, "05_attack_seed_stability", "三个真实攻击种子的逐点结果",
           "全 1,000 张；显示全部种子而非最强种子。MI 每配置生成一次；同种子不代表 CUDA 逐位可复现。",
           bottom=0.18, top=0.91)


def plot_time(summary, budgets, output):
    # Generation is performed only once, then reused across target/subset rows.
    # Confirm this before choosing one representative target's observations.
    for template, *_ in METHODS:
        for g in budgets:
            times = [float(summary[(target, subset, template.format(g))]["mean_attack_seconds"])
                     for target in TARGETS for subset in ("full1000", "pilot200", "new800")]
            if not np.allclose(times, times[0], rtol=0, atol=1e-10):
                raise ValueError("Repeated timing observations unexpectedly disagree")
    fig, axes = plt.subplots(1, 3, figsize=(17.8, 5.8))
    for template, label, color, marker, linestyle in METHODS:
        rows = [summary[(TARGETS[0], "full1000", template.format(g))] for g in budgets]
        times = [float(row["mean_attack_seconds"]) for row in rows]
        axes[0].plot(budgets, times, color=color, marker=marker, linestyle=linestyle,
                     linewidth=1.7, markersize=4.8, label=label)
        for axis, target in zip(axes[1:], TARGETS):
            rows = [summary[(target, "full1000", template.format(g))] for g in budgets]
            axis.plot(times, [float(row["asr"]) * 100 for row in rows],
                      color=color, marker=marker, linestyle=linestyle, linewidth=1.7, markersize=4.8)
            axis.annotate(f"G{budgets[-1]}", (times[-1], float(rows[-1]["asr"]) * 100),
                          xytext=(4, 4), textcoords="offset points", fontsize=8, color=color)
    axes[0].set_title("生成成本：相同 G 不等于相同耗时")
    setup_axis(axes[0], budgets, "全 1,000 张生成耗时（秒／种子）")
    axes[0].set_ylim(bottom=0)
    for axis, target in zip(axes[1:], TARGETS):
        axis.set_title(f"{TARGET_LABELS[target]}｜效果—耗时")
        axis.set_xlabel("全 1,000 张生成耗时（秒／种子）")
        axis.set_ylabel("条件迁移 ASR（%）")
        axis.grid(color="#D8DEE6", linewidth=0.7, alpha=0.8)
    finish(fig, axes, output, "06_time_and_effectiveness", "生成耗时与迁移效果",
           "BSR 为三个种子的单次生成耗时均值，MI 为一次观测；不累加目标或子集中的重复时间。\n"
           "含变换、梯度、GPU 同步及结果转 CPU；不含预热与模型评价。时间曲线不是独立的等时间攻击实验。",
           bottom=0.27, top=0.85)


def plot_subsets(comparisons, budgets, output):
    fig, axes = plt.subplots(2, 2, figsize=(14.4, 9.5))
    for row_index, target in enumerate(TARGETS):
        for column_index, views in enumerate((2, 4)):
            axis = axes[row_index, column_index]
            for subset, label, color, marker, style in (
                ("full1000", "全部 1,000 张", "#3D6F9A", "o", "-"),
                ("new800", "排除早期 pilot 的 800 张", "#B47845", "s", "--"),
            ):
                rows = get_pair(comparisons, target, subset, budgets, views, True)
                draw_pair(axis, budgets, rows, label, color, marker, style)
            axis.set_title(f"{TARGET_LABELS[target]}｜{'双' if views == 2 else '四'}视图 BSR − 固定 MI")
            setup_axis(axis, budgets, "ASR 配对差（百分点）", zero=True)
    finish(fig, axes, output, "07_subset_sensitivity", "图片集合敏感性：全 1,000 张与其中的新增 800 张",
           "误差条为各集合原图片配对 95% 区间，未经多重比较校正。两集合重叠，不构成独立重复。",
           bottom=0.18, top=0.91)


def contact_sheet(output, stems):
    fig, axes = plt.subplots(4, 2, figsize=(16, 13.5))
    for axis, stem in zip(axes.ravel(), stems):
        axis.imshow(plt.imread(output / f"{stem}.png"))
        axis.set_title(stem, fontsize=9)
        axis.axis("off")
    for axis in axes.ravel()[len(stems):]:
        axis.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.98, wspace=0.03, hspace=0.08)
    fig.savefig(output / "qa_contact_sheet.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--extra-comparisons", type=Path)
    args = parser.parse_args()
    run, output = args.run.resolve(), args.output.resolve()
    before = {name: sha(run / name) for name in INPUTS}
    config = json.loads((run / "config.frozen.json").read_text(encoding="utf-8"))
    budgets = sorted(config["gradient_budgets"])
    if config["target_models"] != list(TARGETS) or config["views"] != [1, 2, 4]:
        raise ValueError("These figures require the reviewed two-target, M=1/2/4 run")
    summary = make_index(read_csv(run / "summary.csv"), ("target", "subset", "method"))
    seeds = make_index(read_csv(run / "per_seed.csv"), ("target", "subset", "method", "seed"))
    comparisons = make_index(read_csv(run / "comparisons.csv"), ("target", "subset", "method_a", "method_b"))
    if args.extra_comparisons:
        for key, row in make_index(read_csv(args.extra_comparisons), ("target", "subset", "method_a", "method_b")).items():
            if key in comparisons:
                for field in ("difference_a_minus_b", "ci95_lower", "ci95_upper"):
                    if not np.isclose(float(row[field]), float(comparisons[key][field]), rtol=0, atol=1e-12):
                        raise ValueError(f"Extra table changes an existing comparison: {key}, {field}")
            comparisons[key] = row
    font = configure_font()
    output.mkdir(parents=True, exist_ok=True)
    stems = ["01_asr_full1000", "02_gain_full1000", "03_gain_detail_20_40"]
    plot_asr(summary, budgets, output)
    plot_gains(comparisons, budgets, output)
    plot_gains(comparisons, budgets, output, zoom=True)
    if args.extra_comparisons:
        plot_extra(comparisons, budgets, output)
        stems.append("04_view_and_step_rule_contrasts")
    plot_seeds(summary, seeds, budgets, output)
    plot_time(summary, budgets, output)
    plot_subsets(comparisons, budgets, output)
    stems.extend(["05_attack_seed_stability", "06_time_and_effectiveness", "07_subset_sensitivity"])
    contact_sheet(output, stems)
    after = {name: sha(run / name) for name in INPUTS}
    if before != after:
        raise RuntimeError("Original source artifacts changed while figures were rendered")
    manifest = {"source_run": str(run), "source_sha256": before, "script_sha256": sha(__file__),
                "chinese_font": font, "matplotlib_version": matplotlib.__version__,
                "figure_groups": stems, "png_dpi": 300,
                "x_axis": "actual numeric gradient budgets; no categorical equal spacing",
                "asr_shading": "BSR observed min-max attack seed range, not a confidence interval",
                "paired_intervals": "original image paired percentile 95% bootstrap, not multiplicity adjusted or a crossover confidence interval",
                "model_inference_calls": 0, "attacks_generated": 0, "api_calls": 0,
                "artifacts_sha256": {path.name: sha(path) for path in sorted(output.glob("*"))
                                     if path.is_file() and path.name != "figures-manifest.json"}}
    if args.extra_comparisons:
        manifest["extra_comparisons_sha256"] = sha(args.extra_comparisons)
    (output / "figures-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figures": len(stems), "output": str(output), "font": font, "source_hashes_preserved": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
