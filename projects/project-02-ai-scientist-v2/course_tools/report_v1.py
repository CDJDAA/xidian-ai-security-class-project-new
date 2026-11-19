"""Export a completed V1 pilot into a compact, reviewable course report."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = (
    "results.json", "summary.csv", "predictions.csv", "comparison.png", "examples.png",
    "config.frozen.json", "selection.json", "provenance.json",
)


def percentage(value):
    return "N/A" if value is None else f"{100 * value:.2f}%"


def export_report(run, destination, junit=None):
    run, destination = Path(run).resolve(), Path(destination).resolve()
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    provenance = json.loads((run / "provenance.json").read_text(encoding="utf-8"))
    config = json.loads((run / "config.frozen.json").read_text(encoding="utf-8"))
    by_name = {cfg["name"]: cfg for cfg in config["methods"]}
    bsr_config = by_name["bsr10x4_g40"]
    if results["stage"] != "pilot" or (run / "failure.json").exists():
        raise ValueError("Only a completed successful pilot can be exported")
    if hashlib.sha256((run / "config.frozen.json").read_bytes()).hexdigest() != provenance["config_sha256"]:
        raise ValueError("Frozen config hash mismatch")
    if hashlib.sha256((run / "selection.json").read_bytes()).hexdigest() != provenance["selection_sha256"]:
        raise ValueError("Frozen selection hash mismatch")
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for relative in EVIDENCE:
        shutil.copyfile(run / relative, destination / relative)
        hashes[relative] = hashlib.sha256((destination / relative).read_bytes()).hexdigest()
    verification = {"artifacts_sha256": hashes, "exporter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if junit is not None:
        xml = ET.parse(junit).getroot()
        suites = [xml] if xml.tag == "testsuite" else list(xml.iter("testsuite"))
        verification["pytest_junit"] = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
    (destination / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# V1 首轮预实验：等梯度预算下 BSR 与 MI-FGSM", "",
        f"完成时间：{results['completed_at']}。这是 {results['images']} 张固定图片、一个 BSR 基础种子、一个源/目标组合的真实预实验。", "",
        "## 实验条件", "",
        f"- 源模型：`{results['source']}`；目标模型：`{results['target']}`。",
        f"- CIFAR-10，非定向 L∞，epsilon={config['epsilon']:.10f}（{config['epsilon']*255:g}/255），零起点，batch={config['batch_size']}。",
        f"- BSR 每轴 {bsr_config['blocks']} 块、±{bsr_config['rotation_degrees']:g}° 双线性旋转、零填充，batch 内共享随机几何；每批种子为 {config['attack_seed']} 加批次号。",
        "- 配置、类别平衡且固定打乱的测试 IDs、源码和模型哈希先冻结；攻击全部生成后，目标模型才在本次进程中参与测试评价。",
        "- 目标不提供攻击梯度，也不用于挑选参数。全测试集干净准确率用于检查权重/预处理，攻击结果仅针对固定预实验子集。",
        "- 本实验没有调用模型服务，API 调用数为 0。", "",
        "## 正常推理与约束", "",
        f"源模型完整测试集干净准确率：{percentage(results['source_full_test_clean']['accuracy'])}（{results['source_full_test_clean']['correct']}/{results['source_full_test_clean']['count']}）。",
        f"目标模型完整测试集干净准确率：{percentage(results['target_full_test_clean']['accuracy'])}（{results['target_full_test_clean']['correct']}/{results['target_full_test_clean']['count']}）。", "",
        f"四组攻击合计执行 {results['total_sample_view_gradient_evaluations']:,} 次样本–视图梯度评估，预热另列。逐图像素和 L∞ 约束全部通过。", "",
        "## 对照结果", "",
        "| 方法 | 每图梯度 G | 步长 α | 目标成功数/原图认对数 | 目标迁移 ASR | 源白盒 ASR | 攻击耗时/s | 峰值分配显存/MiB |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in results["methods"].items():
        target, source, generation = item["target"], item["source"], item["generation"]
        lines.append(
            f"| {name} | {generation['gradient_evaluations_per_image']} | {by_name[name]['alpha']*255:.3f}/255 | "
            f"{target['asr_numerator']}/{target['asr_denominator']} | {percentage(target['asr'])} | "
            f"{percentage(source['asr'])} | {generation['attack_seconds']:.3f} | {generation['peak_cuda_allocated_mib']:.1f} |"
        )
    lines.extend([
        "", "ASR 分母是该目标在同一批原图上认对的图片数；全体图片的扰动后准确率另见 CSV。", "",
        "![迁移成功率与耗时](comparison.png)", "",
        "## 配对差及其不确定性", "",
        "下表为 BSR 减去各基线的 ASR 差，单位为百分点；95% 区间来自按图片聚类的配对 bootstrap，条件于本次模型及种子。", "",
        "| 比较 | 差值/百分点 | 95% 区间/百分点 |", "| --- | ---: | --- |",
    ])
    for name, comparison in results["paired_comparisons"].items():
        delta, interval = comparison["difference_a_minus_b"], comparison["ci95"]
        difference = "N/A" if delta is None else f"{100*delta:+.2f}"
        ci = "N/A" if interval is None else f"[{100*interval[0]:+.2f}, {100*interval[1]:+.2f}]"
        lines.append(f"| {name} | {difference} | {ci} |")
    lines.extend([
        "", "MI-10 是低预算参考；主要对照是 MI-40，另完整报告 MI-40 大步长敏感性。不能只选择有利步长或比较对象。", "",
        "## 固定顺序样例", "", "![固定顺序样例](examples.png)", "",
        "上图取冻结顺序的前 8 张，未按攻击成功挑选。", "",
        "## 复现与原始证据", "",
        "按 [V1 运行指南](../../../guides/v1-experiments.md) 准备环境与资产，在项目 02 根目录执行：", "",
        "```bash", "python -m course_tools.v1_assets --offline",
        "python -m pytest tests/test_v1_attacks.py tests/test_v1_metrics.py tests/test_v1_runner.py -q",
        "python -m course_tools.run_v1 --stage develop",
        "python -m course_tools.run_v1 --stage pilot --config configs/v1_budget.json", "```", "",
        "- [本次冻结配置](config.frozen.json)、[数据 IDs](selection.json)、[来源与环境](provenance.json)。",
        "- [逐图预测](predictions.csv)、[汇总 CSV](summary.csv)、[完整指标与配对区间](results.json)。",
        "- [证据 SHA256 与测试摘要](verification.json)。",
        f"- 本机原始运行目录：`experiments/{run.name}/`，含完整对抗样本、每组计数及源码快照，未复制权重或完整对抗样本到报告。", "",
        "## 局限与后续", "",
        "这是小样本预实验，尚未完成第二目标、多个 BSR 种子、预算曲线、ImageNet 复现、防御评价或完整论文生成。",
        "固定随机种子控制采样，但 CUDA 双线性旋转反传可能不确定。区间不包含独立训练或全部攻击随机性的变化。",
        "相同 G 不保证相同 FLOPs 或耗时；表中耗时是单轮同步观测，含变换和结果转 CPU，不含预热及目标评价，不能当作稳定时间效率结论。",
        "保持本次参数冻结后，优先扩展预先声明的样本与第二目标，并增加 BSR 种子；如改变协议，应记录版本并使用预留的新评价样本。",
        "没有观察到优势不等于证明方法等价；本报告不声称提出新算法或达到发表所需的新颖性。", "",
    ])
    (destination / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--junit", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    destination = args.output or ROOT / "docs/reports" / results["completed_at"][:10] / "v1-budget"
    export_report(run, destination, args.junit)


if __name__ == "__main__":
    main()
