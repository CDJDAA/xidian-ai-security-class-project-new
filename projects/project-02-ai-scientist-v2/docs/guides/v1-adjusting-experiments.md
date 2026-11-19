# 自己调整 V1：从配置到攻击循环

这份指南的目标是让你能回答三个问题：改哪个值、程序实际会做什么、结果应怎样解释。阅读顺序建议为：本指南 → `configs/v1_crossover.json` → `build_methods()` → `run_attack()`。

原来的 `run_v1_full` 用于复现已经完成的固定实验，仍锁定 G=20/40/80、M=1/2/4、三个 BSR 种子及两个目标。它的参数校验、方法生成、配对比较和报告都有固定条件，不能只改 JSON 或删除一条报错就当成可调版本。

新的 `course_tools.run_v1_sweep` 是可调参数的探索入口，使用相同的攻击核心和统计函数，独立保存运行记录。探索结果可以帮助选下一轮设置，但不能把看过结果后选出的设置称为事先未看结果的确认实验。

## 1. 先理解程序怎样花掉梯度预算

核心关系：**每图梯度预算 G = 更新步数 T × 每步视图数 M**。

```text
JSON 配置
   ↓ read_config：检查预算、种子、模型等是否有效
build_methods：把 G 和 M 转成 T、alpha 及方法列表
   ↓ build_jobs：MI 每配置一次；BSR 每配置 × 每个种子
run_batched：按固定图片顺序分 batch，实际种子 = 基础种子 + batch 编号
   ↓ run_attack：只访问源模型，生成所有对抗样本
目标模型 predict：只作评价，不给攻击提供梯度
   ↓ 逐图预测 → 每种子结果 → 汇总 ASR 与配对差
CSV / JSON
```

在[攻击核心](../../course_tools/v1_attacks.py)的 `run_attack()` 中，关键逻辑可以简化为：

```python
for step in range(T):                    # 外层：更新几次
    mean_gradient = 0
    for view_index in range(M):         # 内层：一次更新看几个视图
        view = transform(x) if BSR else x
        loss = cross_entropy(source_model(view), labels)
        gradient = grad(loss, x)         # 对当前原坐标图像求梯度
        mean_gradient += gradient / M

    momentum = decay * momentum + normalize(mean_gradient)
    x = x + alpha * sign(momentum)
    x = project_to_epsilon_ball_and_valid_pixels(x)
```

这是理解用的简化代码，不能直接替代原函数。内层每个视图分别求梯度，再平均；外层才更新图片。梯度预算按每张图片计，batch 中 20 张一起反传不意味着只消耗一张图片的计算量。

例如 G=30：

| 方法 | M | T | 每步 alpha | 实际每图梯度次数 |
| --- | ---: | ---: | --- | ---: |
| 固定步长 MI | 1 | 30 | epsilon / 10 | 30 |
| 双视图 BSR | 2 | 15 | epsilon / 15 | 30 |

固定步长 MI 的 alpha 不随 T 改变；BSR 延续已有规则 alpha=epsilon/T。这是本实验对照的具体定义，不是只改变变换、其他优化行为完全相同的机制实验。

epsilon 是最终允许的像素改动上限；alpha 是每一步尝试走多远。即使 MI 多走几步，投影仍把最终扰动限制在 epsilon 内，两者不能混为一个参数。

## 2. 平时改配置，不用改梯度代码

示例配置是 [configs/v1_crossover.json](../../configs/v1_crossover.json)。先复制为自己的名字，在副本中修改；不要编辑已有运行目录里的 `config.frozen.json`。

最先学习以下字段：

```json
{
  "gradient_budgets": [20, 24, 30, 36, 40],
  "views": [1, 2],
  "mi_step_rules": ["fixed"],
  "bsr_seeds": [42, 142, 242],
  "fixed_step_denominator": 10
}
```

这是字段片段，不是可直接覆盖完整配置的 JSON。各字段含义：

| 想研究的变量 | 配置字段 | 改动后会发生什么 |
| --- | --- | --- |
| 多大的预算开始值得用 BSR | `gradient_budgets` | 每个 G 产生一组相同梯度预算的对照 |
| 每步看多少个 BSR 变体 | `views` | 1 表示原始 MI；大于 1 表示对应 BSR 的 M，T 自动取 G/M |
| 攻击随机性 | `bsr_seeds` | 每个 BSR 配置真实重跑这些种子，报告均值，不取最大值 |
| MI 步长规则 | `mi_step_rules` | `fixed` 使用 epsilon/D；`epsilon_over_steps` 使用 epsilon/T，可同时保留 |
| 固定 MI 走多大一步 | `fixed_step_denominator` | D 越大，每步越小；不要在找预算交叉点时一起调整它 |
| 换源模型 | `source_model` | 改变生成对抗样本时求梯度的模型，需要重新生成攻击 |
| 换目标模型 | `target_models` | 改变迁移评价对象，目标不参与求梯度；新的运行会重新生成本次攻击 |
| 扰动上限 | `epsilon` | 改变问题难度，当前 8/255≈0.03137255；同组对照保持相同 |
| BSR 空间变换强度 | `blocks`、`rotation_degrees` | 改变分块数和旋转角，属于另一个实验变量 |
| batch 大小 | `batch_size` | 影响显存，也改变共享随机变换的分组，不能当成完全不影响结果的性能开关 |
| 区间数值稳定程度 | `bootstrap_replicates` | 只增加统计重采样，不增加攻击次数，也不会改善模型表现 |
| 统计抽样的可复现性 | `bootstrap_seed` | 控制统计重采样，不是 BSR 攻击种子 |

两个重要约束：

1. **每个 G 都必须被每个 BSR 的 M 整除。** 双视图可用 G=24、30、36；G=25、35 不行。不能用 `G // M` 悄悄舍去余数，再把实际 24 次写成 25 次。若额外加入四视图，则所有 G 都要是 4 的倍数，例如 20、24、28、32、36、40。奇数预算可以设计最后一步只算一个视图，但这需要另一种明确记录的攻击日程，当前入口不采用。
2. **基础种子之间要留足 batch 数的间隔。** 当前 1000 张、batch=20，共 50 批；程序使用 base_seed+batch_index，因此 `[42,142,242]` 的三段不重叠，而 `[42,43,44]` 会重叠。增加种子可用 `[42,142,242,342,442]`。若缩小 batch，先重新计算 `ceil(1000/batch_size)`，再检查间隔。

本入口继续固定原来的 1,000 张编号及顺序；`sample_count`、`selection_source` 与 `selection_sha256` 不能随意修改。换新图片需要另写并冻结抽样清单、排除已有编号、核对类别分布和哈希，不能只把 1000 改成 2000。

当前资产注册表只支持以下三个已核验的预训练模型：`cifar10_resnet20`、`cifar10_mobilenetv2_x1_0`、`cifar10_vgg11_bn`。源模型必须与目标不同；不能随意写一个模型名就认为会自动下载。

## 3. 在你自己的电脑上运行

先进入 Ubuntu（这条在 PowerShell 执行）：

```powershell
wsl -d Ubuntu -u zst
```

后续在 Ubuntu 执行。Windows 的 E 盘项目和 Ubuntu 的 `/home/zst/projects/` 是两份目录。下面从 E 盘读取你正在编辑的配置，运行程序和依赖来自 Ubuntu 项目；新增入口已经同步到 Ubuntu。

```bash
cd /home/zst/projects/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2
source .venv/bin/activate
```

复制示例配置并编辑 E 盘副本：

```bash
cp /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/configs/v1_crossover.json /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/configs/v1_crossover_mine.json
nano /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/configs/v1_crossover_mine.json
```

也可以直接用 Windows 编辑器修改 E 盘的 `v1_crossover_mine.json`。JSON 里不能写注释，最后一个元素后面不能多逗号。

**第一步总是先看计划，不跑 GPU：**

```bash
python -m course_tools.run_v1_sweep \
  --config /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/configs/v1_crossover_mine.json \
  --plan
```

核对每行 G、M、T、alpha 是否符合预期。默认配置有 5 个预算，每个预算是 MI 一次及 BSR 三个种子，共 **20 个生成任务、600,000 次 sample-view 梯度计算**；预热开销另计。增加目标模型不增加这部分攻击梯度，因为同一批对抗样本复用于各目标。

确认计划后才正式运行，输出目录换成一个尚不存在的名字：

```bash
python -m course_tools.run_v1_sweep \
  --config /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/configs/v1_crossover_mine.json \
  --output /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/experiments/v1_crossover_mine_01
```

这才会实际运行 CUDA 攻击。你能在 Windows 的 `E:\SecAI-code\xidian-ai-security-class-project-new\projects\project-02-ai-scientist-v2\experiments\v1_crossover_mine_01` 找到结果。

中断后恢复时，把同一命令的 `--output` 改为 `--resume`，使用原目录，并保持配置、执行源码、模型和数据不变。**修改任何实验设置后，创建新输出目录；不要拿新配置恢复旧运行。**

如果以后修改 E 盘的 Python 源码，Ubuntu 副本不会自动更新。这里只修改 JSON 时，上面的绝对 `--config` 路径可以避免读错配置；修改源码则需要先同步相应文件并重新验证。

## 4. 第一次练习：把翻转范围缩小

本轮只改变预算，保留 source、target、epsilon、两个视图、固定 MI 步长、batch、图片顺序和种子：

| G | MI 的 T | 双视图 BSR 的 T |
| ---: | ---: | ---: |
| 20 | 20 | 10 |
| 24 | 24 | 12 |
| 30 | 30 | 15 |
| 36 | 36 | 18 |
| 40 | 40 | 20 |

输出中先看：

- `summary.csv`：每个配置的 ASR、步数、alpha 和种子数。
- `per_seed.csv`：种子之间是否稳定，不能只摘最高的一次。
- `comparisons.csv`：筛选目标 MobileNetV2、`subset=full1000`、`method_a=bsr_m2_g...`、`method_b=mi_g..._fixed_step`，看差值与区间。
- `predictions.csv`：需要重新统计时的逐图证据，不手改预测。
- `config.frozen.json`、`selection.json`、`provenance.json`：本次究竟运行了哪份配置、数据及源码。

`difference_a_minus_b` 的单位是比例，例如 `0.025` 表示高 **2.5 个百分点**，不是高 0.025 个百分点，也不是相对提升 2.5%。

假设补点后 G=30 的均值差为负、G=36 为正，可以先说“本轮采样点的均值翻转落在 30–36 之间”，下一轮再补 32、34。这里的数值是假设，不是已完成结果。不要把连线与零轴的交点当成精确阈值；如果附近区间都跨零，或者差值多次正负翻转，就还没有证据确定一个稳定、唯一的交叉点。所得范围也只适用于这里的模型、数据、步长规则和种子。

探索入口输出 CSV/JSON，不要把新的任意矩阵传给 `report_v1_full`、`render_v1_full_figures` 或 `plot_v1_gains`，这些旧报告程序仍针对原完整矩阵。

## 5. 第二次练习：增加种子与步长对照

一次只研究一个问题：

```json
"bsr_seeds": [42, 142, 242, 342, 442]
```

这会增加真实的 BSR 生成任务。与之不同，把 `bootstrap_replicates` 从 2000 改成 10000，只是反复抽取已有结果来估区间，绝不等于多跑了八千次攻击。

再单独增加 MI 的另一种步长规则：

```json
"mi_step_rules": ["fixed", "epsilon_over_steps"]
```

这样每个预算多一个 MI 配置，避免结论只对某一种 MI 步长成立。先想清楚要比较什么，再修改配置；不要同时调 epsilon、旋转、视图、步长和源模型，最后无法解释结果变化来自哪里。

## 6. 多重比较是统计程序的设置，不是攻击参数

你提的 24 个对照有具体口径：在一个图片集合内，2 个目标 × 3 个预算 × 2 种 BSR × 2 种 MI = 24。再加 M4−M2 是 30；原报告的三个集合合计 90 行。新探索配置如果只保留一个目标、五个预算、双视图与固定 MI，则只有 5 个配对对照，家族大小随研究主张而变。

Holm 和 BH 的输入是**有效的原始 p 值**，不是已有置信区间。Holm 控制一整组检验至少一次误报的概率；BH 控制被判有差异的发现中的错误比例，两者不应混称。见 [statsmodels 接口](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html)和 [R 官方解释](https://stat.ethz.ch/R-manual/R-devel/library/stats/html/p.adjust.html)。

计算逻辑是：

```python
# 先按相同 test_id 对齐，仅保留目标原图预测正确的图片。
bsr_success = success_by_seed.mean(axis=0)  # 先在每张图内平均 seed
difference = bsr_success - mi_success       # 每张图片一个配对差
# 原始 batch 内允许相关，按 batch 聚类，得到均值的近似 SE 和双侧 p。
# 收齐整个预先定义的家族后，再统一校正：
reject, p_holm, _, _ = multipletests(p_raw_all, alpha=0.05, method="holm")
```

不能把三个种子的 3×1000 行当成 3000 张独立图片；不能根据已经看到的大效应，只挑几个赢家组成很小的校正家族。原图片 bootstrap 区间仍单独保留，不能把它两端乘 24 后叫“Holm 区间”。若需要同时区间，可以另报告清楚标注的 Bonferroni 近似区间。当前附加统计入口采用按原 batch 聚类的均值标准误与 t 近似，推断仍条件于现有模型和攻击种子，不替代独立确认。

独立统计入口只读取保存结果，不运行模型：

该入口额外使用 SciPy 的 t 分布函数。部署本机已经补装；在另一台已具备课程环境的机器上，只需在激活 `.venv` 后执行一次 `uv pip install -r requirements-v1-analysis.txt`。依赖版本单独记录在[可选统计依赖](../../requirements-v1-analysis.txt)，不需要重新安装 PyTorch。

```bash
python -m course_tools.v1_multiplicity \
  --run /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-full \
  --subset full1000 --family bsr_vs_mi --plan
```

查看完整 24 项后，将 `--plan` 改成新的输出路径，例如：

```bash
python -m course_tools.v1_multiplicity \
  --run /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/docs/reports/2026-11-18/v1-full \
  --subset full1000 --family bsr_vs_mi \
  --output /mnt/e/SecAI-code/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2/experiments/v1_holm_mine_01
```

`--subset new800` 则单独检查新增 800 张；这与全 1000 张有重叠，不是独立重复。`--family all` 还包含已有 M4−M2 对照。Holm 是本次敏感性分析的主列，BH 作为带依赖假设的探索列；两者都依赖原始检验近似合理。

“校正后不显著”应写成“尚无足够证据证明有差异”，不能写成“已证明没有差异”。要证明实用意义上的等效，需要先指定可接受的差异范围，再做等效检验；见[配对等效检验说明](https://www.statsmodels.org/stable/generated/statsmodels.stats.weightstats.ttost_paired.html)。同样，大效应是否保留要看实际校正结果，不提前承诺一定通过。

本机已经跑了一份实例：[24 项家族的实际分析记录](../reports/2026-11-18/v1-multiplicity/README.md)。Mobile G80 双视图相对固定 MI 的 +6.55 个百分点在本方法下 Holm p≈8.01e-8；Mobile G40 双视图的 +2.17 个百分点则为 p≈0.121，未通过 0.05。这正好说明为何要把大效果与边缘小效果分开陈述。以上是已有数据的条件性敏感性分析，并未新增攻击。

## 7. 每次实验留下四句话

```text
问题：这轮只想确认什么？
改动：相对哪份配置，只改了哪些值？
结果：所有设置的差值、区间、种子波动是什么？
解释：支持哪一条有边界的判断，还不能说明什么？
```

先用 `--plan` 理解一次配置如何变成任务，再实际运行；保留负结果和区间，往往比不断加入新参数更有研究价值。
