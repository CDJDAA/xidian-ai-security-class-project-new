# 用户独立运行结果：中文表格与可视化

对应原始运行 `experiments/v1_crossover_manual_01`，完成于 2026-11-18 17:45:49（北京时间）。本目录仅整理已保存结果，没有重新运行模型或攻击。

- **首先打开 [中文结果工作簿](实验结果_中文解读.xlsx)**：“结果总览”看主结果；“配对比较”按目标、预算、方法筛选；“字段说明”解释单位与分母。逐图工作表为固定前八个编号的示例，完整逐图数据在下方 CSV。
- **阅读 [完整对比解读与优化建议](report.md)**：包括所有预算的四方法 ASR、四条 BSR−MI 曲线、双／四视图和两 MI 步长的直接比较、时间与下一步建议。
- **用于汇报的图**：[总体 ASR](figures/01_asr_full1000.png)、[差值全范围](figures/02_gain_full1000.png)、[G20–40 细节](figures/03_gain_detail_20_40.png)、[视图与步长直接对照](figures/04_view_and_step_rule_contrasts.png)、[三个种子](figures/05_attack_seed_stability.png)、[时间成本](figures/06_time_and_effectiveness.png)、[图片集合敏感性](figures/07_subset_sensitivity.png)。每图同目录另有 SVG。
- **完整中文 CSV**：[方法汇总](data/方法汇总_中文.csv)、[种子明细](data/种子明细_中文.csv)、[原配对比较](data/原配对比较_中文.csv)、[112,000 行逐图记录](data/完整逐图预测_中文.csv)。
- **补充配对分析**：[全部 252 行对照](data/all_comparisons.csv)，覆盖每个目标和预算的四方法六种两两比较。统计推断方法与限制在 [report.md](report.md) 中说明。

当前最需要谨慎解释的是 MobileNetV2 双视图对固定 MI 的 G24–G28 均值翻转：两端区间都跨零，G28 种子差值有正有负。VGG 在已采样点没有观察到交叉。所有图表同时保留两种 MI 基线，不只摘取更有利的一套。

原始文件校验、数据加工、绘图和工作簿验证记录见 [verification.json](verification.json)；独立复算见 [audit.json](audit.json)。
