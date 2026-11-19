# V1 参数教学与多重比较敏感性记录

执行日期：2026-11-18。原实验：[V1 完整报告](../v1-full/report.md)。操作教程：[自己调整 V1](../../../guides/v1-adjusting-experiments.md)。

## 本次实际完成什么

1. 新增可调的 `course_tools.run_v1_sweep` 和 `configs/v1_crossover.json`，并在 Ubuntu 用 `--plan` 核对 G=20/24/30/36/40、双视图 BSR 与固定步长 MI。计划为 10 个方法、20 个生成任务、600,000 次 sample-view 梯度。**本次没有执行新的预算点攻击，计划不等于实验结果，交叉点尚未确定。**
2. 新增只读的 `course_tools.v1_multiplicity`，在原 full1000 和 new800 保存预测上分别运行 24 项 BSR−MI 家族的统计敏感性分析。原 50,000 行预测、指标及冻结实验源码未改；没有调用模型、API 或生成新攻击。
3. 在已有 Ubuntu 虚拟环境中添加可选 `scipy==1.16.3`，保留 `numpy==2.4.6`，`uv pip check` 通过。新工具及相关旧模块的检查共 58 项测试和 61 个子测试通过；包括模拟的攻击/评价流程，不是新的 GPU 效果复验。

## 为什么是 24 项

每个集合内：2 个目标 × 3 个预算 × 2 种 BSR 视图数 × 2 种 MI 步长 = 24。没有先挑显著或较大的效果缩小家族。此次不含 M4−M2 的六项对照；包含它们则为 30 项。原报告的三种集合合计 90 行比较。

full1000 与 new800 分别作为两个敏感性分析家族，结果有重叠，**不作为独立重复，也没有宣称控制两个家族合并后的错误率**。

## 方法和边界

每图先平均已保存的 BSR 种子成功指标，减去 MI 成功指标，仅保留目标干净预测正确的图片。图片按原 `final_ids` 位置除以 batch_size=20 分组，以原 batch 为 cluster。对均值差使用截距模型的 CRV1 聚类标准误及 t 近似，df=非空 cluster 数−1。

Holm 校正的近似 p 值是主结果；BH 只列为探索结果，当前相关检验满足其依赖条件尚未验证。另算 Bonferroni cluster-t 近似同时区间；它们不是 Holm/BH 区间。原图片 bootstrap 区间完整保留，未被覆盖。

这些推断条件于现有模型和三个已经实现的攻击种子，依赖聚类近似，不包括更多种子或独立训练的不确定性。校正后未拒绝零差异不代表证明两方法等效。

## 实际关键结果

下表差值均为 BSR−MI，单位为百分点。Mobile 的 MI 为固定步长，VGG 的 MI 为主规则；完整两个步长的结果均列在子报告。

| 目标与预算 | 集合 | ΔASR | Holm p（24 项家族） | 判断 |
| --- | --- | ---: | ---: | --- |
| Mobile 双视图，G40 | full1000 | +2.17 | 0.1209 | 本方法与家族下未拒绝零差异 |
| Mobile 双视图，G40 | new800 | +2.41 | 0.1760 | 本方法与家族下未拒绝零差异 |
| Mobile 双视图，G80 | full1000 | +6.55 | 8.01e-8 | 正向差异在本次校正中保留 |
| Mobile 双视图，G80 | new800 | +6.18 | 5.16e-6 | 正向差异在本次校正中保留 |
| VGG 双视图，G40 | full1000 | +11.62 | 1.09e-12 | 正向差异在本次校正中保留 |
| VGG 双视图，G80 | full1000 | +16.81 | 1.02e-17 | 正向差异在本次校正中保留 |
| Mobile 四视图，G40 | full1000 | -0.11 | 0.9223 | 尚无足够证据证明差异 |
| Mobile 四视图，G40 | new800 | +0.09 | 0.9784 | 尚无足够证据证明差异 |

这支持把 G80 的双视图优势作为主要观察，把 Mobile G40 的微小改进留作边界条件，而不是把所有正均值讲成稳定提升。

## 复算与证据

- [全 1,000 张的完整 24 项](full1000/report.md)：[JSON](full1000/multiplicity.json)、[CSV](full1000/multiplicity.csv)。
- [新增 800 张的完整 24 项](new800/report.md)：[JSON](new800/multiplicity.json)、[CSV](new800/multiplicity.csv)。
- [补点计划](crossover-plan.json)、[本次检查记录与哈希](verification.json)、[测试记录](tests.xml)。

本次命令均在 Ubuntu 项目根目录、现有虚拟环境执行：

```bash
python -m course_tools.run_v1_sweep \
  --config /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/configs/v1_crossover.json --plan
python -m course_tools.v1_multiplicity \
  --run /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-full \
  --subset full1000 --family bsr_vs_mi \
  --output /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-multiplicity/full1000
```

new800 将第二条命令的两个 `full1000`（集合与输出目录末段）改为 `new800`；`--run` 仍指原报告目录。复算时另换一个全新的输出目录，已有目录会被拒绝，避免覆盖。

参考：[Holm/BH 接口](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)、[错误率与依赖条件](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html)、[聚类协方差与组数减一推断](https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.get_robustcov_results.html)。
