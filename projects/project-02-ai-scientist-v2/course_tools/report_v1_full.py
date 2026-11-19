"""Export the completed V1 budget matrix as figures and a Chinese briefing.

This program reads recorded predictions/metrics and cached images. It never
queries a model, generates attacks, or selects new experimental parameters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SUBSETS = ("full1000", "new800")
BUDGETS = (20, 40, 80)
FAMILIES = (
    ("MI-FGSM, alpha=eps/T", "mi_g{}", "#245b93", "o", "-"),
    ("BSR, M=2 (3-seed mean)", "bsr_m2_g{}", "#d87822", "s", "-"),
    ("BSR, M=4 (3-seed mean)", "bsr_m4_g{}", "#21845b", "^", "-"),
    ("MI-FGSM, alpha=eps/10", "mi_g{}_fixed_step", "#6f637e", "D", "--"),
)
EVIDENCE = ("config.frozen.json", "selection.json", "provenance.json", "results.json",
            "summary.csv", "per_seed.csv", "predictions.csv", "comparisons.csv")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def pct(value):
    return "N/A" if value is None else f"{100 * value:.2f}%"


def pp(value):
    return "N/A" if value is None else f"{100 * value:+.2f}"


def interval_text(interval):
    return "N/A" if interval is None else f"[{pp(interval[0])}, {pp(interval[1])}]"


def short_target(name):
    return name.removeprefix("cifar10_").replace("mobilenetv2_x1_0", "MobileNetV2").replace("vgg11_bn", "VGG11-BN")


def human_method(name):
    if name == "mi10_reference":
        return "MI-10 参考"
    if name.startswith("bsr_m"):
        view, budget = name.removeprefix("bsr_m").split("_g")
        return f"BSR M={view}, G={budget}"
    if name.endswith("_fixed_step"):
        return f"MI G={name[4:-11]}, α=ε/10"
    return f"MI G={name.removeprefix('mi_g')}, α=ε/T"


def index_summary(results):
    indexed = {}
    for row in results["summary"]:
        key = (row["target"], row["subset"], row["method"])
        if key in indexed:
            raise ValueError(f"Duplicate summary row {key}")
        indexed[key] = row
    return indexed


def index_comparisons(results):
    indexed = {}
    for row in results["comparisons"]:
        key = (row["target"], row["subset"], row["method_a"], row["method_b"])
        if key in indexed:
            raise ValueError(f"Duplicate comparison row {key}")
        indexed[key] = row
    return indexed


def validate_run(run):
    """Reject incomplete matrices and changed frozen inputs before export."""
    run = Path(run)
    results = load_json(run / "results.json")
    config = load_json(run / "config.frozen.json")
    provenance = load_json(run / "provenance.json")
    selection = load_json(run / "selection.json")
    if results.get("schema_version") != 2 or results.get("stage") != "full" or not results.get("completed_at"):
        raise ValueError("Expected a completed schema-v2 full run")
    if results.get("api_calls") != 0:
        raise ValueError("Unexpected model-service calls in the fixed V1 benchmark")
    completion = load_json(run / "completion.json")
    if completion.get("completed_at") != results["completed_at"]:
        raise ValueError("Completion marker does not match completed results")
    for filename, expected in completion["sha256"].items():
        candidate = (run / filename).resolve()
        if not candidate.is_relative_to(run.resolve()) or sha256(candidate) != expected:
            raise ValueError(f"Completed artifact hash mismatch: {filename}")
    for filename, key in (("config.frozen.json", "config_sha256"), ("selection.json", "selection_sha256")):
        if sha256(run / filename) != provenance[key]:
            raise ValueError(f"Frozen input hash mismatch: {filename}")
    for filename in EVIDENCE:
        if not (run / filename).is_file():
            raise FileNotFoundError(run / filename)
    final_ids, pilot_ids, new_ids = map(set, (selection["final_ids"], selection["pilot_ids"], selection["new_ids"]))
    if len(final_ids) != 1000 or len(pilot_ids) != 200 or len(new_ids) != 800:
        raise ValueError("Unexpected 1000/200/800 selection sizes")
    if any(len(selection[key]) != len(set(selection[key])) for key in ("final_ids", "pilot_ids", "new_ids")):
        raise ValueError("Repeated image IDs in frozen selection")
    if pilot_ids & new_ids or pilot_ids | new_ids != final_ids:
        raise ValueError("Pilot/new subsets must partition the frozen final IDs")
    indexed = index_summary(results)
    comparisons = index_comparisons(results)
    if len(results["targets"]) != 2:
        raise ValueError("The full V1 report expects both target models")
    for target in results["targets"]:
        for subset, expected_count in (("full1000", 1000), ("new800", 800), ("pilot200", 200)):
            for name, metadata in results["methods"].items():
                row = indexed[(target, subset, name)]
                expected_seeds = 3 if metadata["method"] == "bsr" else 1
                if row["attack_seed_count"] != expected_seeds or len(row["per_seed"]) != expected_seeds:
                    raise ValueError(f"Missing seeds in {target}/{subset}/{name}")
                if not 0 <= row["asr_denominator"] <= expected_count:
                    raise ValueError("Invalid conditional ASR denominator")
            for budget in BUDGETS:
                for views in (2, 4):
                    for baseline in (f"mi_g{budget}", f"mi_g{budget}_fixed_step"):
                        comparisons[(target, subset, f"bsr_m{views}_g{budget}", baseline)]
    return results, config, provenance, selection


def save_figure(figure, destination, name):
    figure.savefig(destination / f"{name}.png", dpi=180, bbox_inches="tight")
    figure.savefig(destination / f"{name}.svg", bbox_inches="tight")
    plt.close(figure)


def number(value):
    return np.nan if value is None else float(value)


def seed_bounds(row):
    return number(row.get("asr_seed_min", row["asr"])), number(row.get("asr_seed_max", row["asr"]))


def plot_budget_and_time(results, destination):
    indexed = index_summary(results)
    for subset in SUBSETS:
        for by_time in (False, True):
            fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
            for ax, target in zip(axes, results["targets"]):
                for label, pattern, color, marker, style in FAMILIES:
                    rows = [indexed[(target, subset, pattern.format(budget))] for budget in BUDGETS]
                    xs = [row["mean_attack_seconds"] for row in rows] if by_time else BUDGETS
                    ys = [100 * number(row["asr"]) for row in rows]
                    ax.plot(xs, ys, label=label, color=color, marker=marker, linestyle=style, linewidth=1.7)
                    if rows[0]["attack_seed_count"] > 1:
                        bounds = [seed_bounds(row) for row in rows]
                        ax.fill_between(xs, [100*b[0] for b in bounds], [100*b[1] for b in bounds], color=color, alpha=0.13)
                    if by_time:
                        for x, y, budget in zip(xs, ys, BUDGETS):
                            ax.annotate(f"G={budget}", (x, y), xytext=(3, 4), textcoords="offset points", fontsize=7, color=color)
                ax.set_title(short_target(target))
                ax.set_ylim(0, 100)
                if by_time:
                    ax.set_xlabel("Attack generation time per 1,000 images (s)\nBSR: mean of three separate seeded runs")
                else:
                    ax.set_xlabel("Gradient evaluations per image, G = T x M")
                    ax.set_xticks(BUDGETS)
                ax.grid(alpha=0.22)
            axes[0].set_ylabel("Transfer attack success rate (%)")
            axes[1].legend(fontsize=8, loc="lower right")
            fig.suptitle(f"CIFAR-10 pretrained targets | {subset} | source: ResNet-20\nBSR shading: three-seed range, not a confidence interval", fontsize=11)
            fig.tight_layout(rect=(0, 0.04, 1, 0.90))
            fig.text(0.5, 0.005, "Untargeted Linf eps=8/255; CIFAR-adapted BSR (2 blocks/axis, +/-10 deg). Time is one observed execution, not a timing CI.", ha="center", fontsize=8)
            save_figure(fig, destination, ("asr_vs_time_" if by_time else "asr_vs_budget_") + subset)


def plot_seed_detail(results, destination):
    indexed = index_summary(results)
    method_names = ("mi_g40", "mi_g40_fixed_step", "bsr_m2_g40", "bsr_m4_g40")
    labels = ("MI\neps/T", "MI\neps/10", "BSR\nM=2", "BSR\nM=4")
    colors = ("#245b93", "#6f637e", "#d87822", "#21845b")
    for subset in SUBSETS:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.7), sharey=True)
        for ax, target in zip(axes, results["targets"]):
            for position, (name, color) in enumerate(zip(method_names, colors)):
                row = indexed[(target, subset, name)]
                value = 100 * number(row["asr"])
                ax.bar(position, value, width=0.65, color=color, alpha=0.78)
                per_seed = row["per_seed"]
                offsets = np.linspace(-0.12, 0.12, len(per_seed)) if len(per_seed) > 1 else [0]
                for offset, seed_row, marker in zip(offsets, per_seed, ("o", "s", "^")):
                    ax.scatter(position + offset, 100 * number(seed_row["asr"]), c="white", edgecolors="black", s=36, marker=marker, zorder=4)
                ax.annotate(f"{value:.2f}", (position, value), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
            ax.set_xticks(range(4), labels)
            ax.set_ylim(0, 105)
            ax.set_title(short_target(target))
            ax.grid(axis="y", alpha=0.22)
        axes[0].set_ylabel("Transfer attack success rate (%)")
        fig.suptitle(f"G=40 | {subset} | bars: mean ASR; white markers: each recorded seed", fontsize=11)
        fig.tight_layout(rect=(0, 0.04, 1, 0.92))
        fig.text(0.5, 0.005, "MI is deterministic for this setup; its single marker is not three independent repetitions. BSR uses 42, 142, 242.", ha="center", fontsize=8)
        save_figure(fig, destination, "g40_seeds_" + subset)


def plot_comparisons(results, destination):
    comparisons = index_comparisons(results)
    colors = {20: "#245b93", 40: "#d87822", 80: "#21845b"}
    for subset in SUBSETS:
        fig, axes = plt.subplots(1, 2, figsize=(14, 7.4), sharex=True)
        for ax, target in zip(axes, results["targets"]):
            labels = []
            row_number = 0
            for budget in BUDGETS:
                for views in (2, 4):
                    for suffix, label in (("", "MI eps/T"), ("_fixed_step", "MI eps/10")):
                        comparison = comparisons[(target, subset, f"bsr_m{views}_g{budget}", f"mi_g{budget}{suffix}")]
                        value, interval = comparison["difference_a_minus_b"], comparison["ci95"]
                        if interval is not None:
                            ax.hlines(row_number, 100*interval[0], 100*interval[1], color=colors[budget], linewidth=1.7)
                        if value is not None:
                            ax.plot(100*value, row_number, marker="o" if views == 2 else "s", color=colors[budget], markersize=5)
                        labels.append(f"G{budget}: BSR M{views} - {label}")
                        row_number += 1
            ax.set_yticks(range(len(labels)), labels, fontsize=8)
            ax.invert_yaxis()
            ax.axvline(0, color="black", linestyle="--", linewidth=0.8)
            ax.set_title(short_target(target))
            ax.set_xlabel("Paired ASR difference (percentage points)")
            ax.grid(axis="x", alpha=0.2)
        fig.suptitle(f"{subset}: image-paired 95% bootstrap intervals\nConditional on recorded models and attack seeds; no multiplicity adjustment", fontsize=11)
        fig.tight_layout(rect=(0, 0.04, 1, 0.91))
        save_figure(fig, destination, "paired_differences_" + subset)


def plot_examples(run, results, selection, destination):
    """Show predeclared first images, without success-based selection."""
    import torch
    inputs = torch.load(run / "inputs.pt", map_location="cpu", weights_only=True)
    images = inputs["images"]
    if list(inputs["ids"]) != list(selection["final_ids"]):
        raise ValueError("Example input IDs do not match frozen selection")
    labels = inputs["labels"]
    jobs = results["jobs"]
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    selected = []
    for method in ("mi_g40", "bsr_m4_g40"):
        candidates = [job for job in jobs if job["method"] == method and (method == "mi_g40" or job["seed"] == 42)]
        if len(candidates) != 1:
            raise ValueError(f"Expected one example cache for {method}")
        cached = torch.load(run / candidates[0]["cache_path"], map_location="cpu", weights_only=True)
        if list(cached["ids"]) != list(selection["final_ids"]):
            raise ValueError("Example adversarial IDs do not match frozen selection")
        selected.append(cached["adversarial"])
    n = min(8, len(images))
    fig, axes = plt.subplots(3, n, figsize=(n*1.55, 5.0), squeeze=False)
    for column in range(n):
        for row, tensors in enumerate((images, *selected)):
            axes[row, column].imshow(tensors[column].permute(1, 2, 0).numpy(), interpolation="nearest")
            axes[row, column].set_xticks([])
            axes[row, column].set_yticks([])
        axes[0, column].set_title(f"ID {selection['final_ids'][column]}\ny={int(labels[column])}", fontsize=9)
    for row, label in enumerate(("Clean", "MI G40", "BSR M4 G40\nseed 42")):
        axes[row, 0].set_ylabel(label)
    fig.suptitle("First eight frozen IDs, not chosen by attack success", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save_figure(fig, destination, "examples")


def comparison_description(row):
    value, interval = row["difference_a_minus_b"], row["ci95"]
    if value is None or interval is None:
        return "分母不足，无法计算差值或区间"
    if interval[0] > 0:
        conclusion = "本条件下区间全为正"
    elif interval[1] < 0:
        conclusion = "本条件下区间全为负"
    else:
        conclusion = "区间包含零，当前不能确定优势方向"
    return f"差 {pp(value)} 个百分点，95% 区间 {interval_text(interval)}；{conclusion}"


def g40_table(results, subset):
    indexed = index_summary(results)
    lines = ["| 目标 | 方法 | 平均成功数/原图认对数 | ASR | 各种子 ASR 范围 | 源白盒 ASR | 平均生成时间/s |",
             "| --- | --- | ---: | ---: | --- | ---: | ---: |"]
    for target in results["targets"]:
        for method in ("mi_g40", "mi_g40_fixed_step", "bsr_m2_g40", "bsr_m4_g40"):
            row = indexed[(target, subset, method)]
            numerator = row["asr_numerator"]
            numerator = f"{numerator:g}" if isinstance(numerator, (float, int)) else str(numerator)
            minimum, maximum = row.get("asr_seed_min"), row.get("asr_seed_max")
            lines.append(f"| {short_target(target)} | {human_method(method)} | {numerator}/{row['asr_denominator']} | {pct(row['asr'])} | {pct(minimum)}–{pct(maximum)} | {pct(row['source_asr'])} | {row['mean_attack_seconds']:.3f} |")
    return lines


def all_comparison_table(results, subset):
    lines = ["| 目标 | G | BSR 视图数 | MI 步长 | ASR 差/百分点 | 95% 区间/百分点 |",
             "| --- | ---: | ---: | --- | ---: | --- |"]
    comparisons = index_comparisons(results)
    for target in results["targets"]:
        for budget in BUDGETS:
            for views in (2, 4):
                for suffix, label in (("", "ε/T"), ("_fixed_step", "ε/10")):
                    row = comparisons[(target, subset, f"bsr_m{views}_g{budget}", f"mi_g{budget}{suffix}")]
                    lines.append(f"| {short_target(target)} | {budget} | {views} | {label} | {pp(row['difference_a_minus_b'])} | {interval_text(row['ci95'])} |")
    return lines


def write_report(run, destination, results, config, selection, verification):
    comparisons = index_comparisons(results)
    source_clean = results["source_full_test_clean"]
    lines = ["# V1 完整实验：固定梯度预算下的空间视图与迭代深度", "",
             f"完成时间：{results['completed_at']}。本报告来自已完成的本机 CUDA 实验，源码、冻结配置、数据 IDs、权重哈希与逐图预测均有对应记录。", "",
             "## 研究问题与方法", "",
             "同样的计算预算，用于更多 MI-FGSM 更新，还是用于每轮更多 BSR 空间变换视图，哪种分配更有利于黑盒迁移？本实验评价已存在攻击策略的资源分配，不声称提出新攻击算法。", "",
             "源模型 ResNet-20 提供梯度。攻击生成时只使用源模型；所有对抗样本生成并缓存后，分别交给 MobileNetV2 和 VGG11-BN 评价，两目标共用完全相同的对抗样本。三个模型均使用来源明确的 CIFAR-10 预训练权重，模型参数保持冻结。", "",
             "非定向 L∞，ε=8/255，零起点，动量系数 1。BSR 使用每轴 2 块、±10°、双线性插值、零填充，随机几何在 batch 内共享。它是 CIFAR 小图适配配置，不能直接当作原论文 ImageNet 复现。", "",
             "每图预算 G=T×M。M=1 端点使用原图 MI-FGSM；BSR 使用 M=2/4，T=G/M，主步长 α=ε/T。每个 G 另设 MI α=ε/10 的敏感性对照，保留 MI-10 低预算参考。", "",
             "| G | MI 步数/原图 | BSR M=2 步数 | BSR M=4 步数 | MI 固定步长敏感性 |",
             "| ---: | ---: | ---: | ---: | --- |",
             "| 20 | 20 | 10 | 5 | α=ε/10，20 步 |",
             "| 40 | 40 | 20 | 10 | α=ε/10，40 步 |",
             "| 80 | 80 | 40 | 20 | α=ε/10，80 步 |", "",
             "BSR 每配置运行基础种子 42、142、242，报告每种子及其均值；MI 在此零起点、eval 配置下每配置运行一次。种子平均不是 best-of-three，也不代表三个独立训练模型。", "",
             "## 数据与评价口径", "",
             "沿用首轮预先固定的 1,000 张 CIFAR-10 测试 IDs，每类 100 张。该集合包含首轮 200 张，所以分别报告 full1000、pilot200 和 new800。new800 是未参与首轮攻击效果评价的 800 张，并非从未访问过目标：首轮已经检查过完整测试集的干净准确率。", "",
             "本轮按完整 1,000 张的冻结顺序重新生成攻击，pilot200 指本轮生成结果中对应的子集。BSR 在 batch 内共享几何，图片与批次的对应关系可能不同，因此即使基础种子仍为 42，该子集也不是旧的独立 200 张运行的原样缓存或精确重现；旧预实验记录另行保留。", "",
             "ASR 分母为每个目标、每个子集上原图认对的数量；所有方法共享该目标/子集的分母。全体固定图片上的扰动后准确率另行报告，不以 1−ASR 直接替代。", "",
             "所有配置提前冻结，不依据本轮目标结果挑块数、角度、步长、种子或目标。三个种子按同一图片聚合；配对 bootstrap 每次将同一图片的所有方法/种子一起重采样。95% 区间条件于本次固定模型与已记录种子，不包含独立训练的不确定性；多组对照区间未作多重比较校正。", "",
             "## 模型正常推理与计算核验", "",
             f"源模型完整测试集准确率：{pct(source_clean['accuracy'])}（{source_clean['correct']}/{source_clean['count']}）。", "",
             "| 目标 | 完整测试集干净准确率 | 正确数/总数 |", "| --- | ---: | ---: |"]
    for target, metadata in results["targets"].items():
        clean = metadata["full_test_clean"]
        lines.append(f"| {short_target(target)} | {pct(clean['accuracy'])} | {clean['correct']}/{clean['count']} |")
    lines.extend(["", f"本轮实际攻击生成合计 {results['total_sample_view_gradient_evaluations']:,} 次样本–视图梯度评估。25 个生成任务的结果复用于两个目标；预热/开发诊断计算另列。每个视图合批不减少 G 计数。", "",
                  "## G=40 的主对照", "", "### 全部 1,000 张", "", *g40_table(results, "full1000"), "",
                  "### 未参与首轮攻击效果评价的 800 张", "", *g40_table(results, "new800"), "",
                  "BSR 成功数是三个种子的平均，可出现小数。时间为每配置一次种子执行的均值，均按完整 1,000 张生成计时；new800 只是在同一批缓存上重新评价，不能把这个时间称为单独生成 800 张的耗时。目标数增加前向评价成本，不增加重复攻击生成成本。", "",
                  "## 预算曲线与种子变化", ""])
    for subset, title in (("full1000", "全部 1,000 张"), ("new800", "新增 800 张")):
        lines.extend([f"### {title}", "", f"![ASR–梯度预算 {subset}](asr_vs_budget_{subset}.png)", "",
                      f"![ASR–时间 {subset}](asr_vs_time_{subset}.png)", "",
                      f"![G40 各种子 {subset}](g40_seeds_{subset}.png)", ""])
    lines.extend(["曲线阴影表示三个 BSR 种子的范围，不是置信区间；它展示变换随机性。相同 G 不保证相同 FLOPs 或耗时。计时含变换、GPU 同步与结果转 CPU，不含预热、源/目标评价；这是单次执行的观测，未做独立计时重复。", "",
                  "## 配对差与可支持的结论", "",
                  "主比较为 BSR 减去同 G 的 MI 主基线，并完整保留 MI 固定步长敏感性；区间包含零表示当前证据不足以确定差异方向，不表示已证明等价。", ""])
    for subset, title in (("full1000", "全部 1,000 张"), ("new800", "新增 800 张")):
        lines.extend([f"### {title}", "", f"![配对 ASR 差 {subset}](paired_differences_{subset}.png)", "", *all_comparison_table(results, subset), ""])
    lines.extend(["### G=40 的直接解读", ""])
    for target in results["targets"]:
        for views in (2, 4):
            base = comparisons[(target, "new800", f"bsr_m{views}_g40", "mi_g40")]
            sensitivity = comparisons[(target, "new800", f"bsr_m{views}_g40", "mi_g40_fixed_step")]
            lines.append(f"- {short_target(target)}、新增 800 张、BSR M={views}：相对主 MI，{comparison_description(base)}；相对固定步长 MI，{comparison_description(sensitivity)}。")
    lines.extend(["", "这些观察仅支持当前源模型、两个预训练目标、数据和参数范围内的条件性判断。不能由某一目标、某一种子或某个预算的最高点推导出 BSR 普遍更好，也不能把参考模型间梯度方向称为已知的理想方向。", "",
                  "## 固定顺序的图像样例", "", "![固定顺序图像](examples.png)", "",
                  "图像来自冻结顺序的前八张；显示原图、MI G40 及 BSR M4 G40 的 seed42，未按攻击成功选择样例。", "",
                  "## 复现与审查入口", "",
                  "```bash", "source .venv/bin/activate", "python -m course_tools.v1_assets --offline",
                  "python -m course_tools.run_v1_full --config configs/v1_full.json",
                  f"python -m course_tools.report_v1_full --run experiments/{run.name}", "```", "",
                  "- [冻结配置](config.frozen.json)、[数据 IDs](selection.json)、[模型/环境/代码来源](provenance.json)。",
                  "- [汇总](summary.csv)、[各随机种子](per_seed.csv)、[逐图预测](predictions.csv)、[配对差](comparisons.csv)、[完整结果](results.json)。",
                  "- [图表和证据 SHA256、测试摘要](verification.json)。每张图另附同名 SVG，便于放入汇报。",
                  f"- 原始缓存与源码快照保留在 `experiments/{run.name}/`；本报告不复制全部 `.pt`、模型权重或数据集。",
                  "- 源码：[完整运行器](../../../../course_tools/run_v1_full.py)、[攻击核心](../../../../course_tools/v1_attacks.py)、[统计](../../../../course_tools/v1_metrics.py)、[报告程序](../../../../course_tools/report_v1_full.py)。",
                  "- [完整协议](../../../research/v1-full-protocol.md)与[运行指南](../../../guides/v1-experiments.md)。", ""])
    if "pytest_junit" in verification:
        summary = verification["pytest_junit"]
        lines.extend([f"本次附带的 pytest JUnit 记录 {summary['tests']} 个 case（可能包含子测试），失败 {summary['failures']}、错误 {summary['errors']}、跳过 {summary['skipped']}。软件测试验证实现约束，不代替研究效果证据。", ""])
    lines.extend(["## 局限与后续", "",
                  "本阶段完成的是 CIFAR 上的一条源模型、两个目标、三个攻击种子及三个计算预算的 V1 评价。尚未实施训练检查点 V2、更多代理训练重复、ImageNet/Transformer 全面复现、防御评价或自动论文生成。",
                  "CUDA 双线性旋转反传可能不完全确定，固定种子主要控制采样；本报告不承诺位级一致。BSR 的共享 batch 几何与当前 batch/顺序共同构成实验条件。",
                  "全 1,000 张包含已看到的 200 张；新增 800 张单独呈现。报告任何新协议或参数选择时，都应另留评价数据，避免把已参与选择的目标结果当成独立确认。",
                  "后续工作由这些条件性结果决定；无论是否观察到 BSR 优势，本阶段都能交付可复现代码、完整对照、预算与时间分析，以及限制说明。", ""])
    (destination / "report.md").write_text("\n".join(lines), encoding="utf-8")


def write_briefing(destination, results):
    indexed, comparisons = index_summary(results), index_comparisons(results)
    lines = ["# V1 汇报理解与讲稿", "",
             "## 一句话介绍", "",
             "我们研究同样的梯度计算预算，应该用来多更新几轮，还是每轮多参考几种空间变换。我们用一个白盒模型制作攻击图片，再交给两个未参与攻击生成的目标模型检验迁移效果。", "",
             "## 这次实际完成了什么", "",
             "- 1,000 张固定 CIFAR-10 图片，每类 100 张；把其中曾评价过的 200 张和新增 800 张分别统计。",
             "- ResNet-20 提供梯度，MobileNetV2 与 VGG11-BN 负责检验；三个模型使用公开预训练权重，模型参数没有重新训练。",
             "- 每图梯度预算为 20、40、80；MI 用原图多走几步，BSR 每步看 2 或 4 个变换视图。",
             "- BSR 每配置使用 3 个种子，报告平均及各种子结果；MI 每个确定性配置运行一次。",
             "- 保留统一主步长规则及固定步长敏感性，保存全部预测、计数、图表和可复现配置。", "",
             "## 源码可以这样介绍", "",
             "`v1_assets.py` 准备和核验数据/预训练模型；`v1_attacks.py` 实现 MI、BSR、投影和实际梯度计数；`run_v1_full.py` 冻结协议、调度 25 个生成任务、共用缓存评价两个目标；`v1_metrics.py` 计算条件 ASR 和图片配对区间；`report_v1_full.py` 读取已经记录的结果，生成图表和这份讲稿。实验没有调用 DeepSeek API。", "",
             "## 指标怎么理解", "",
             "攻击成功指目标原来认对、加入扰动后认错。分母是该目标在这一批原图上认对的数量；因此不同目标的分母可以不同。同一目标下所有方法使用相同分母。梯度次数相等不代表耗时相等，BSR 还有图像变换开销。", "",
             "## 报告 G=40 的真实结果", ""]
    for target in results["targets"]:
        main = indexed[(target, "new800", "mi_g40")]
        fixed = indexed[(target, "new800", "mi_g40_fixed_step")]
        bsr2 = indexed[(target, "new800", "bsr_m2_g40")]
        bsr4 = indexed[(target, "new800", "bsr_m4_g40")]
        lines.extend([f"### {short_target(target)}，新增 800 张", "",
                      f"目标原图认对 {main['asr_denominator']} 张。MI 主规则 ASR {pct(main['asr'])}，固定步长 MI {pct(fixed['asr'])}，BSR M=2 三种子均值 {pct(bsr2['asr'])}，BSR M=4 三种子均值 {pct(bsr4['asr'])}。", ""])
        for views in (2, 4):
            difference = comparisons[(target, "new800", f"bsr_m{views}_g40", "mi_g40_fixed_step")]
            lines.append(f"BSR M={views} 相对固定步长 MI：{comparison_description(difference)}。")
        lines.append("")
    lines.extend(["## 图表按什么顺序讲", "",
                  "1. 先用预算曲线介绍每个目标上四种分配策略随 G 的变化，完整展示两个目标。",
                  "2. 再看 G40 种子图，解释 BSR 的均值与随机变化；种子最高值不代表平均性能。",
                  "3. 用配对差图说明差多少、区间是否跨零；不把跨零说成两方法相等。",
                  "4. 最后展示时间曲线：梯度预算下的收益与实际秒数下的收益是两个口径。", "",
                  "## 可以直接使用的开场", "",
                  "> 我们已完成固定梯度预算下的 V1 批量实验，包含一千张 CIFAR-10 图片、三个 BSR 随机种子、两个预训练目标模型和二十、四十、八十的梯度预算。每组攻击只在 ResNet-20 上生成一次，再复用于两个目标。我们同时保留主步长和固定步长 MI 对照，并单独报告未参与首轮攻击效果评价的八百张结果。接下来我会从预算、种子变化、目标差异和实际耗时四个角度介绍观察到的结果。", "",
                  "## 回答老师可能追问的问题", "",
                  "- **是黑盒还是白盒？** 对源模型是白盒，对最终目标是基于迁移的黑盒；目标梯度不参与生成。",
                  "- **自己训练模型了吗？** 这次用公开 CIFAR 预训练权重并核验来源和正常准确率；研究重点是攻击预算分配。",
                  "- **BSR 一定更强吗？** 按当前每个预算、目标及步长对照报告，不能由单点最高值断言普遍更强。",
                  "- **三种子等于三次模型训练吗？** 不等于，它们只改变 BSR 的随机变换，源/目标权重相同。",
                  "- **为什么单独看八百张？** 一千张包含首轮已评价的二百张；单列新增部分，避免把扩展结果说成全部首次评价。",
                  "- **是不是复现了论文全部结果？** 这是 CIFAR 小图上的机制适配与实证评价，未声称完成 ImageNet 全量复现。", "",
                  "完整数值、配对区间、图片与局限见 [实验报告](report.md)，所有曲线另附 SVG，可直接用于汇报排版。", ""])
    (destination / "briefing.md").write_text("\n".join(lines), encoding="utf-8")


def export_report(run, destination, junit=None):
    run, destination = Path(run).resolve(), Path(destination).resolve()
    results, config, provenance, selection = validate_run(run)
    destination.mkdir(parents=True, exist_ok=False)
    for filename in EVIDENCE:
        shutil.copyfile(run / filename, destination / filename)
    plot_budget_and_time(results, destination)
    plot_seed_detail(results, destination)
    plot_comparisons(results, destination)
    plot_examples(run, results, selection, destination)
    verification = {"exporter_sha256": sha256(__file__), "api_calls_during_export": 0,
                    "artifacts_sha256": {}, "raw_run_directory": "experiments/" + run.name}
    if junit is not None:
        xml = ET.parse(junit).getroot()
        suites = [xml] if xml.tag == "testsuite" else list(xml.iter("testsuite"))
        verification["pytest_junit"] = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
    write_report(run, destination, results, config, selection, verification)
    write_briefing(destination, results)
    for path in sorted(destination.iterdir()):
        if path.is_file():
            verification["artifacts_sha256"][path.name] = sha256(path)
    write_json(destination / "verification.json", verification)
    print(destination, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--junit", type=Path)
    args = parser.parse_args()
    results = load_json(args.run / "results.json")
    destination = args.output or ROOT / "docs/reports" / results["completed_at"][:10] / "v1-full"
    export_report(args.run, destination, args.junit)


if __name__ == "__main__":
    main()
