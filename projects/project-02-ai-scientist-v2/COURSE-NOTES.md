# 项目 02 环境与改动记录（课程作业）

> 对应课程任务 `COURSE.md` 第 1 条：记录环境版本、运行命令和最小示例结果。
> 上游版本：`96bd51617cfdbb494a9fc283af00fe090edfae48`（课程目录整理时记录）

## 1. 实际运行环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows 11 Pro 10.0.26200 |
| CPU | Intel Core i7-10700 @ 2.90GHz（8 核 16 线程） |
| 内存 | 31.7 GB |
| GPU | AMD Radeon RX 640 4 GB + Intel UHD 630 —— **无 NVIDIA，无 CUDA** |
| Conda | conda 26.7.1（`D:\miniconda3`） |
| Python | 3.11.17（环境名 `course-scientist-v2`） |
| Git | 2.55.0.windows.3 |
| 模型服务 | 校内 OpenAI 兼容服务 `https://hyymodels.xidian.edu.cn/v1`，模型 `DeepSeek-V4.1-Flash-1017` |

与上游要求的差异：上游要求 Linux + NVIDIA GPU + CUDA + PyTorch。本机不满足，因此**本次只运行想法生成阶段**（不涉及训练），实验树搜索阶段留待后续。

## 2. 环境创建与依赖安装

```bash
conda create -n course-scientist-v2 python=3.11 -y
conda activate course-scientist-v2
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

`requirements.txt` 不包含 PyTorch，所以想法生成阶段在纯 CPU 环境可运行。实测安装 74 个包（含 `openai 3.35.1`、`anthropic 1.17.0`、`backoff 2.2.1`）。

**未安装 PyTorch**：实验阶段才需要，届时应安装 CPU 版：

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## 3. 模型配置

```bash
export OPENAI_API_KEY="<校内服务密钥>"          # Windows: set $env:OPENAI_API_KEY
export AISCI_BASE_URL="https://hyymodels.xidian.edu.cn/v1"
export PYTHONUTF8=1                            # 中文 Windows 必需，见下文
```

凭据只放在本机 conda 环境的 `activate.d` 脚本里，**未写入代码仓库**。

## 4. 为跑通所做的代码适配（相对上游的改动）

上游只支持写死的几家模型服务商，且假设 Linux/UTF-8 环境。为在校内服务 + 中文 Windows 上运行，共做 5 处改动：

| 文件 | 改动 | 原因 |
| --- | --- | --- |
| `ai_scientist/llm.py` | `AVAILABLE_LLMS` 增加 `DeepSeek-V4.1-Flash-1017`；`create_client`、`get_response_from_llm`、`make_llm_call` 增加对应分支（走 `AISCI_BASE_URL`） | 上游无此模型，会直接 `ValueError: Model ... not supported` |
| `ai_scientist/llm.py` | `MAX_NUM_TOKENS` 4096 → 8192 | 推理模型会先输出大量 reasoning token，4096 时常出现"思考写满、正文为空" |
| `ai_scientist/tools/semantic_scholar.py` | 无 `S2_API_KEY` 时直接跳过检索（`AISCI_ALLOW_S2=1` 可恢复）；重试 `max_tries=2` 且 `timeout=15` | 匿名请求被 429 限流，原代码 `backoff` 无限重试，实测卡死 8 分钟以上 |
| `ai_scientist/perform_ideation_temp_free.py` | JSON 解析改用 `JSONDecoder().raw_decode` | 模型会在 JSON 后追加 `<assistant>` 等文本，`json.loads` 报 `Extra data` |
| `ai_scientist/perform_ideation_temp_free.py` | 动作解析取"最后一个 `FinalizeIdea`"，默认不提供检索工具 | 模型一次响应会输出多个 `ACTION` 块，上游只取第一个，导致真正的 `FinalizeIdea` 被丢弃 |

另：中文 Windows 下 Python 默认用 GBK 读文件，直接运行会 `UnicodeDecodeError`，需 `PYTHONUTF8=1` 或 `python -X utf8`。

## 5. 最小示例：运行命令与结果

```bash
cd projects/project-02-ai-scientist-v2
python -X utf8 ai_scientist/perform_ideation_temp_free.py \
  --workshop-file ai_scientist/ideas/course_topic.md \
  --model DeepSeek-V4.1-Flash-1017 \
  --max-num-generations 1 \
  --num-reflections 2
```

**结果**：生成成功，`ai_scientist/ideas/course_topic.json` 写入 1 条想法，字段完整
（`Name` / `Title` / `Short Hypothesis` / `Related Work` / `Abstract` / `Experiments` / `Risk Factors and Limitations`）。

- 想法名：`feature_redundancy_tabular_robustness`
- 标题：*Feature Redundancy, Not Model Capacity, Drives Adversarial Robustness in Tabular Data*
- 单次调用统计：`completion_tokens=4065`（其中 reasoning 2965）、`prompt_tokens=1143`、耗时约 40 秒

使用的研究主题（`course_topic.md`）已改写为人工智能安全方向：轻量表格分类器在特征扰动攻击下的鲁棒性，并明确约束为 CPU 单进程、10 分钟内、不超过一万行数据。

## 6. 复现步骤

1. 按第 2 节创建环境并安装依赖。
2. 按第 3 节设置三个环境变量（密钥替换为自己的）。
3. 确认 `ai_scientist/ideas/course_topic.md` 存在。
4. 执行第 5 节命令，检查同目录生成 `course_topic.json`。
5. 用 `python -c "import json;print(len(json.load(open('ai_scientist/ideas/course_topic.json',encoding='utf-8'))))"` 验证条数。

## 7. 已知限制

- **未跑实验阶段**：`launch_scientist_bfts.py` 需要执行模型生成的训练代码，本机无 NVIDIA GPU，CPU 下极易触发 `exec.timeout: 3600` 超时，本次未验证。
- **未启用文献检索**：无 `S2_API_KEY`，想法中的 Related Work 来自模型自身知识，未经检索核验，存在失实风险。
- **样本量小**：`--max-num-generations 1 --num-reflections 2`，只验证流程可通，不代表想法质量。
- **仓库为部分克隆**：因完整仓库 814 MB、本机到 GitHub 实测约 59 KB/s，使用 `--depth 1 --filter=blob:none --sparse` 只检出本项目目录，其他项目目录本地不存在。
- 模型输出格式不稳定，同一条命令多次运行可能得到不同结构与质量的结果。
