# V1 实验运行指南

在项目 02 根目录的 Ubuntu / WSL2 环境中运行。研究问题、预算和评价规则见 [V1 协议](../research/v1-budget-protocol.md)。这些命令运行固定实验代码，不调用 DeepSeek 或其他模型服务。

## 0. 本机先进入正确的终端和目录

本机虚拟环境、数据和权重已经配置在 Ubuntu 的项目副本中。先在 **Windows PowerShell** 执行：

```powershell
wsl -d Ubuntu -u zst
```

进入 Ubuntu 后，终端提示符通常以 `$` 结束。以下三行在 **Ubuntu Bash** 中执行：

```bash
cd /home/zst/projects/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2
source .venv/bin/activate
python -m course_tools.v1_assets --offline
```

看到资产清单 JSON 且没有报错，表示数据和权重核验成功。本机已实际验证这组命令。Windows 的 `E:\SecAI-code\...` 是另一份编辑用工作树；运行实验时进入上面的 Linux 项目目录，那里才有本次配置的 `.venv`、`data/` 和 `cache/v1/`。

`source` 是 Bash 命令，直接在提示符为 `PS ...>` 的 PowerShell 中运行会报错。切换终端后还需要执行 `cd`；只打开 Ubuntu 并不代表已经进入项目目录。

| 报错 | 处理 |
| --- | --- |
| 无法识别 `source` | 先执行上面的 `wsl` 命令进入 Ubuntu |
| `.venv/bin/activate: No such file or directory` | 执行完整 `cd` 命令，确认使用 Ubuntu 中已部署的项目副本 |
| `No module named course_tools` | 回到项目 02 根目录执行，不要在 `docs/` 或 `course_tools/` 内执行 |
| `No module named torch` | 激活本项目 `.venv`；可用 `which python` 确认解释器路径中包含项目的 `.venv/bin/python` |

`v1_assets` 负责准备或核验数据与模型。真正运行对照实验使用第 3 节的 `python -m course_tools.run_v1 --stage pilot`。

## 1. 首次部署时准备数据和模型

使用已验证的 Python 3.11 / CUDA PyTorch 虚拟环境：

```bash
source .venv/bin/activate
python -m course_tools.v1_assets
```

首次准备命令需要联网；上面第 0 节的 `--offline` 核验不联网。准备命令下载官方 CIFAR-10、固定提交的模型定义和原作者权重；当前源码、预处理配置和三份权重均核验固定的完整 SHA256。权重通过 `weights_only=True` 加载，未调用远程 `torch.hub` 入口。缓存中的模型源码保留原作者版权与 BSD 许可证。

数据位于 `data/`，模型、许可证和来源清单位于 `cache/v1/`，均不提交 Git。查看准备结果时读取 `cache/v1/assets-manifest.json`。再次离线核验：

```bash
python -m course_tools.v1_assets --offline
```

模型的归一化在包装器内部，扰动与 epsilon 始终定义在 `[0,1]` 原始像素空间。

## 2. 验证实现并做开发检查

```bash
python -m pytest tests/test_v1_attacks.py tests/test_v1_metrics.py tests/test_v1_runner.py -q
python -m course_tools.run_v1 --stage develop
```

开发检查使用固定的 CIFAR 训练集子集，输出源模型的原图/变换图表现、变换样例和 8 张图片的四组完整攻击测速，不读取最终目标的测试指标。训练集图片可能参与公开权重的训练，不能称为训练外验证集。

每次运行输出独立的 `experiments/v1_develop_<时间>/`。检查 `development.json` 与 `development_transforms.png`；该阶段的梯度计算单独记录，不混入每图攻击预算。

## 3. 运行首轮预实验

```bash
python -m course_tools.run_v1 --stage pilot --config configs/v1_budget.json
```

[固定配置](../../configs/v1_budget.json) 默认是 200 张类别平衡测试图片，ResNet-20 为源，MobileNetV2 x1.0 为目标，epsilon=8/255、batch=20、攻击基础种子 42。包含 MI-10、MI-40、BSR-10×4、MI-40 大步长敏感性四组。

运行器先保存配置、200/1,000 张测试 IDs、资产哈希和源码快照，再生成所有攻击，最后加载目标模型作评价。不能根据这批结果选参后仍把同一批图片称为未参与选择的最终评价。固定顺序和 batch 大小；BSR 几何参数在 batch 内共享，每批种子为基础种子加批次编号。CUDA 双线性旋转反传可能不完全确定，固定随机种子不等于位级一致。

输出位于 `experiments/v1_pilot_<时间>/`：

| 文件 | 用途 |
| --- | --- |
| `config.frozen.json`、`selection.json` | 本次实际配置与预先选定的数据 IDs |
| `provenance.json`、`source_snapshot/` | 环境、模型/数据/源码哈希与源码快照 |
| `results.json`、`summary.csv` | 各方法指标、计时、显存和配对差区间 |
| `predictions.csv` | 每图标签、原图/扰动预测、成功指示、范数及预算 |
| `*.generation.json`、`*.pt` | 实际梯度计数和完整对抗样本，仅留本机 |
| `comparison.png`、`examples.png` | 对照图与按固定顺序展示的样例 |
| `failure.json` | 如果失败，记录失败类型和时间；不能当成成功结果 |

ASR 只把目标原图认对的图片作为分母；扰动后准确率仍覆盖全部固定图片。主要比较 BSR 与 MI-40，MI-10 只是较低预算参考。相同梯度次数不等于相同耗时；攻击计时含变换、GPU 同步及结果转到 CPU，不含预热和目标评价。

200 张、一个 BSR 种子是一轮预实验。配对 bootstrap 区间以图片为重采样单位，不能证明跨训练、跨模型或跨数据集的一般规律。

## 4. 整理课程成果

从原始运行中选择配置、来源、逐图 CSV、汇总和图片，放入对应日期的 `docs/reports/` 并写明局限。原始权重、数据、完整对抗样本与大量日志留在被忽略的目录中；不要手改原始指标或把计划中的实验写成已完成。

本运行器实现四组固定预实验。预算曲线、第二目标和多种子扩展须另行冻结配置与检查统计，不能仅修改方法名称就认为现有绘图/比较逻辑自动适配。

## 5. 完整 V1：1,000 张、三个种子、两个目标和预算曲线

完整扩展采用独立入口 `course_tools.run_v1_full`，旧 `run_v1 --stage pilot` 仍用于复现原四组预实验。研究规则见 [完整 V1 协议](../research/v1-full-protocol.md)。本节命令在 Ubuntu 的项目 02 根目录执行，先激活现有 `.venv`。

```bash
python -m course_tools.v1_assets --offline
python -m course_tools.run_v1_full --config configs/v1_full.json \
  --output /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/experiments/v1_full_my_run
```

需要先将新版源码与配置同步到 Ubuntu，且完成新增 VGG11-BN 资产准备。`--offline` 会核验三个模型；本机已配置后的复现不需要重新训练模型。首次缺少新增资产时，按第 1 节的联网准备流程获取并核验。

`--output` 指向 E 盘的全新目录，目录名可自行更换；已有目录会报错，避免覆盖旧实验。计算仍由 Ubuntu 的 Python 与 CUDA 执行，数据/权重仍从 Linux 项目缓存读取。

Windows 可直接打开 `E:\SecAI-code\xidian-ai-security-class-project-new\projects\project-02-ai-scientist-v2\experiments\v1_full_my_run`。Ubuntu 可进入输出目录，再执行 `explorer.exe .` 查看文件。旧实验默认输出在 `/home/zst/.../experiments/`，两种位置由本次 `--output` 决定，不会自动同步两个项目副本。

完整程序复用原来冻结的 1,000 张 IDs，执行 25 个生成任务，并复用同一批对抗样本评价两个目标。结果同时报告 full1000、pilot200 与 new800。MI 每配置只生成一次，BSR 每配置使用基础种子 42、142、242；BSR 结果取种子平均，不取最强种子或成功并集。

中断后用原目录恢复：

```bash
python -m course_tools.run_v1_full --config configs/v1_full.json \
  --resume /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/experiments/v1_full_my_run
```

恢复仅复用配置、IDs、源码及缓存哈希匹配的完整任务；不覆盖冻结清单，不把未完成缓存当结果。

完成后导出汇报材料到一个新的报告目录：

```bash
python -m course_tools.report_v1_full \
  --run /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/experiments/v1_full_my_run \
  --output /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-full-my-run
```

报告包含 `report.md`、`briefing.md`、CSV 与 PNG/SVG 图。完整对抗样本和源码快照继续留在 `experiments/`。重新运行请使用新的输出目录与报告目录，不覆盖已有证据。

将预算/时间图的共享图例放到图外、避免标注重叠，可继续执行一次只读数据的排版步骤：

```bash
python -m course_tools.render_v1_full_figures \
  --report /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-full-my-run
```

该步骤更新图表与其哈希，不重新生成攻击或评价模型。已完成的本次完整实验见[完整报告](../reports/2026-11-18/v1-full/report.md)和[汇报讲稿](../reports/2026-11-18/v1-full/briefing.md)。

查看相对 MI 的收益大小及区间，可从同一记录补画差值图：

```bash
python -m course_tools.plot_v1_gains \
  --report /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-full-my-run
```

差值图以 0 为无差异参考，保留正负结果、全部目标/视图数/基线及区间，不更改原始 ASR。

## 6. 自己调整后续实验

原完整入口和报告用于复现冻结矩阵。补预算点、修改视图数或增加种子，请先读[参数与代码逻辑教程](v1-adjusting-experiments.md)，使用独立的 `course_tools.run_v1_sweep` 及 `configs/v1_crossover.json`。先加 `--plan` 查看实际步数、步长与任务成本，再决定是否执行攻击；多重比较使用独立的只读统计入口。
