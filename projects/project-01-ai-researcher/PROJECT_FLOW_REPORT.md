# AI-Researcher 自动研究流程梳理（源码阅读报告）

## 1. 报告目的与范围

本文依据项目源码梳理 AI-Researcher 从用户输入到研究实验、论文生成的大致流程，说明主要入口、模块职责、模块之间的数据传递，以及当前流程的边界。

## 2. 项目整体目标

AI-Researcher 将自动研究过程组织成多个阶段：接收研究想法或参考论文，检索论文和代码资源，形成研究想法/实施计划，生成并运行实验代码，再分析实验结果。项目还包含一个论文写作入口，用于根据已有研究材料生成论文各章节并编译 LaTeX。

因此，它不是单一的对话 Agent，而是由工作流调度、多个专职 Agent、外部检索工具、Docker 执行环境和论文生成模块组成的研究自动化系统。

## 3. 入口与运行模式

### 3.1 Web 入口

`web_ai_researcher.py` 提供 Gradio 界面，收集用户输入、参考资料和所选模式，并通过 `main_ai_researcher.py` 调用相应流程。它还负责展示任务日志等界面功能。

### 3.2 流程协调入口

`main_ai_researcher.py` 读取 `.env` 中的类别、任务实例、模型、容器名、工作目录、缓存路径、端口和迭代次数等配置，再按模式分发：

| 模式 | 用户提供的主要内容 | 调用入口 |
| --- | --- | --- |
| `Detailed Idea Description` | 详细研究想法及参考资料 | `research_agent/run_infer_plan.py` |
| `Reference-Based Ideation` | 参考论文，由系统进一步构思想法 | `research_agent/run_infer_idea.py` |
| `Paper Generation Agent` | 已有研究领域和实例 ID | `paper_agent/writing.py` |

前两种是研究与实验流程的两种起点；论文生成是单独的入口，依赖目标目录中已有的研究材料/章节模板，并不等于前两种流程结束后必然自动调用。

## 4. 自动研究主流程

```text
用户输入 + benchmark 实例
          │
          ▼
加载任务、参考论文和任务说明
          │
          ▼
检索论文相关 GitHub 仓库
          │
          ▼
Prepare Agent 选择参考代码库 ── 下载相关论文源码/资料
          │
          ├── 详细想法模式：Survey Agent 调研想法与参考材料
          │
          └── 参考文献模式：Idea Agent 生成多个候选想法并筛选，
                            Code Survey Agent 调研候选想法和代码库
          │
          ▼
Coding Plan Agent 生成实现计划
          │
          ▼
ML Agent 生成项目代码，并按流程要求运行训练和测试
          │
          ▼
Judge Agent 检查实现；按配置决定是否迭代修改
          │
          ▼
提交阶段运行实验 → Experiment Analyser 分析结果并提出后续实验
          │
          └── 形成实验分析与后续改进建议

独立论文写作入口：
方法 → 相关工作 → 实验 → 引言 → 结论 → 摘要 → 清理/处理 LaTeX → 编译 PDF
```

上图是对代码组织和提示词中流程的概括。实际运行结果会受模型响应、外部服务、Docker、数据集、GPU 和配置影响。

## 5. 关键阶段说明

### 5.1 加载任务与 benchmark

研究流程从 `benchmark/final/<CATEGORY>/<INSTANCE_ID>.json` 读取任务实例。实例通常包含目标论文信息、参考论文、任务说明和 arXiv URL。`load_instance` 会读取所选任务级别的说明，并尝试获取论文发布日期，形成后续 Agent 使用的任务元数据。

类别相关的数据集说明、基线、对比结果和评测指标由 `benchmark/process/dataset_candidate/<category>/metaprompt` 等模块提供，供构思或计划阶段参考。启动流程时还会调用 `setup_dataset` 配置工作区数据。

### 5.2 检索与准备参考资源

工作流逐篇参考论文执行 GitHub 仓库检索，将搜索结果交给 Prepare Agent。Prepare Agent 负责挑选参考代码库；其结构化回答随后被解析，用于确定论文/代码资源下载。相关实现分布在 `research_agent/inno/tools/` 和 `research_agent/inno/agents/inno_agent/prepare_agent.py`。

这里的检索结果是后续调研和计划的上下文，不应直接等同于“已验证的高质量依据”。报告实验时应记录实际检索到的资源，并人工核对其相关性、版本和可用性。

两个研究入口在将 Prepare Agent 输出交给下载阶段前，会校验 JSON 中 `reference_codebases`、`reference_paths` 和 `reference_papers` 均为非空字符串列表。若输出无法解析或字段不符合结构，流程会在交接处以明确错误停止，而不是继续运行到后续阶段才因缺字段失败。

### 5.3 两种构思路径

**详细想法模式（`run_infer_plan.py`）**

用户已经提供研究想法。系统将想法、参考论文、检索到的代码库和下载材料交给 Survey Agent，形成调研笔记；然后 Coding Plan Agent 综合调研笔记和类别数据集信息生成实现计划。

**参考文献模式（`run_infer_idea.py`）**

用户主要提供参考论文。系统先准备参考代码和论文资料，再由 Idea Agent 针对 benchmark 任务生成多个候选想法（源码中设定为 5 个），并要求 Agent 选择、完善其中一个。随后 Code Survey Agent 结合下载的代码库形成实现调研报告，再由 Coding Plan Agent 生成实现计划。

两条路径的前半段不同，但都会进入代码生成、评审和实验环节。

### 5.4 代码实现、评审与实验

ML Agent 根据研究想法、调研结果、代码库和计划生成实验项目。源码传给它的要求包括：使用实际数据、实现模型和训练/测试流程，并按提示运行两轮训练和测试。代码执行环境由 Docker 环境模块提供。

随后 Judge Agent 检查实现是否符合想法和计划。`MAX_ITER_TIMES` 控制部分“评审后修改”的轮数；它不是整个流程运行次数的简单开关。之后流程还会进入提交/实验阶段，并由 Experiment Analyser 分析结果、提出后续实验建议，再将建议交回 ML Agent 继续改进。

需要注意：Agent 提示词中写有“必须使用 GPU 和实际数据”等要求，但提示词要求不等于已经成功执行。是否真的完成训练、测试和得到有效指标，必须以容器输出、日志及结果文件为证据。

### 5.5 论文生成

`paper_agent/writing.py` 按固定顺序调用章节生成模块：方法、相关工作、实验、引言、结论、摘要；之后清理和处理 LaTeX 文件，并尝试编译主 tex 文件生成 PDF。它使用 `research_field` 和 `instance_id` 定位论文目录。

这一写作流程和研究 Agent 流程在代码中是分开的入口。论文文件存在不自动证明论文中的实验数据真实、结论可靠或所有章节与实验输出一致，仍需人工核验来源和结果。

## 6. 主要代码位置

| 文件/目录 | 职责 |
| --- | --- |
| `main_ai_researcher.py` | 读取配置并分发三种运行模式 |
| `web_ai_researcher.py` | Gradio 用户界面及日志展示 |
| `research_agent/run_infer_plan.py` | 已有详细想法时的研究、计划、实现和实验流程 |
| `research_agent/run_infer_idea.py` | 从参考论文构思想法后进入实现和实验流程 |
| `research_agent/inno/agents/inno_agent/` | Prepare、Idea、Survey、Plan、ML、Judge、实验分析等专职 Agent |
| `research_agent/inno/tools/` | 论文/代码检索、下载、文件与终端等工具 |
| `research_agent/inno/environment/` | Docker、浏览器和文件访问等执行环境 |
| `benchmark/final/` | 研究任务实例 |
| `benchmark/process/` | benchmark 数据与类别元信息处理 |
| `paper_agent/writing.py` | 论文各章节生成与 LaTeX 编译调度 |
| `paper_agent/` | 各章节写作、模板和论文领域相关模块 |

## 7. 输入、输出与证据关系

| 阶段 | 主要输入 | 预期输出/证据 |
| --- | --- | --- |
| 任务加载 | benchmark JSON、任务级别 | 任务元数据、任务说明 |
| 文献/代码检索 | 参考论文、类别任务 | 检索结果、候选仓库与论文资源 |
| 构思/调研 | 用户想法或参考论文、检索材料 | 候选/选定想法、调研笔记 |
| 计划 | 想法、调研笔记、数据集和基线信息 | 实施计划 |
| 实现与实验 | 想法、计划、参考代码、数据 | 生成代码、训练/测试日志、指标 |
| 评审与分析 | 代码、计划、实验输出 | 修改建议、实验分析、后续计划 |
| 论文生成 | 章节所需材料、模板和实验结果 | tex 文件及可能生成的 PDF |

这条证据链是课程分析的重点：应检查检索材料是否进入调研，调研结论是否进入计划，计划中的方法是否出现在实现里，以及论文里的实验结论是否能由日志和指标支持。不能仅凭 Agent 的文字陈述认定每个环节已经正确完成。

## 8. 建议的小规模复现与后续填写

完整研究流程依赖模型 API、外部检索、Docker 和数据/算力，直接复现全链路成本较高。可先选一个边界清晰的环节，例如 benchmark 实例加载与元数据提取，使用仓库已有 JSON 做本地验证；或针对 Agent 输出的 JSON 解析编写边界用例。完成后应补充以下信息：

- 复现模块与选择理由：
- 环境版本：
- 输入样例/数据：
- 实际运行命令：
- 代码修改及修改前后的差异：
- 验证结果（附命令输出或测试结果）：
- 未验证部分与局限：

以上内容目前留空，表示尚未进行对应复现，不应视作已完成结果。

## 9. 局限与阅读结论

1. 多个阶段依赖 LLM 生成内容，输出具有随机性；检索与生成结果需要人工核实。
2. Agent 之间主要通过消息文本和上下文变量传递内容；结构化结果解析失败可能影响后续阶段。
3. 实验执行依赖容器、数据和硬件条件。代码要求运行实验并不保证任务实际完成，也不保证运行结果有效。
4. 代码实现、实验分析和论文写作是多个阶段/入口，必须追踪实际文件和日志来确认它们是否衔接成功。
5. 本报告是静态源码梳理，尚未验证完整运行链路，也没有声称已复现实验或生成论文。

总体而言，AI-Researcher 的核心是把“检索—构思—计划—实现—实验—评审—分析”组织成带工具执行能力的多 Agent 工作流，并提供独立的论文写作流程。课程复现可从其中一个模块入手，再用实际输入输出说明它在整体流程中的作用。

## 10. 参考文件

- `COURSE.md`
- `README.md`
- `main_ai_researcher.py`
- `research_agent/run_infer_plan.py`
- `research_agent/run_infer_idea.py`
- `research_agent/inno/agents/inno_agent/`
- `research_agent/inno/tools/`
- `research_agent/inno/environment/`
- `paper_agent/writing.py`
