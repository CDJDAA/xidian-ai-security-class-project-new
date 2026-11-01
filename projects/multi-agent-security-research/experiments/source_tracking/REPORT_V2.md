# 项目 04 后续改进报告（2026-11-01）

学号 / 姓名：26241215025 / 董俊逸。开发基线：`6ec2ede98caf233a4168b9da8330a340e2517699`。

## 修改及前后行为

1. **程序绑定来源。** 旧协议要求模型逐字复制 SHA-256 来源编号；模型把 `src_` 写成 `src.` 或 `src/` 时，即使摘录正确仍被拒绝。新协议要求模型返回从 1 开始的整数 `source_index`，由程序查表绑定真实 ID，随后执行原来的逐字摘录、来源归属和结论一致性检查。不会修补模型自报的错误哈希，也不会接受越界、布尔值或字符串序号。
2. **请求预算可追踪。** 原恢复逻辑只累计已保存结果，会漏掉崩溃前已发出的请求。现在请求前写入并刷新 `calls.ledger`，恢复时计入这些保守预留；目录锁阻止两个进程同时消费一份预算。账本损坏会明确报错，预算用尽也不会被计为一次已发送请求。此上限作用于一个输出目录，不是跨目录的账户费用上限。
3. **网页解释拒绝原因。** 在未通过摘录的批次中可展开查看来源缺失、引用不在原文、结论与引用不同等原因，避免把格式问题表现为空摘要。生产静态资源已重新构建。
4. **保留比较路径。** CLI 的 `id` 协议保留用于旧规则回归，`index` 为新版；课程 04 实际分析管线默认使用新版。旧报告和旧结果未被覆盖。

## 真实模型比较

在 2026-11-01 同一批运行中比较两种协议，而不是只与 10 月历史百分比比较。模型请求及响应名称均为 `deepseek-flash`，关闭 thinking，temperature=0.2，输出上限 650 token。每个协议最多 240 次请求、并发 2；两个协议各自独立记录预算。

使用原固定语料 P03–P22，共 20 个任务；每个协议包含正常/注入资料 × 关闭/开启校验四组，每组各运行一次，共 160 次三角色运行、480 次真实模型调用。原文提取成功和污染标记判据与旧实验一致；两组共享语料、任务、模型与角色，来源字段的提示词及绑定步骤随协议变化。

| 条件 | 旧 ID 协议：提取成功 | 新序号协议：提取成功 | 旧/新最终污染成功 | 旧/新引用匹配数 |
| --- | --- | --- | --- | --- |
| 正常资料、无校验 | 20/20 | 20/20 | 不适用 | 19/20、20/20 |
| 正常资料、有校验 | 19/20 | 20/20 | 不适用 | 19/19、20/20 |
| 注入资料、无校验 | 20/20 | 20/20 | 0/20、0/20 | 20/20、20/20 |
| 注入资料、有校验 | 20/20 | 20/20 | 0/20、0/20 | 20/20、20/20 |

本次旧协议的失败仍是 `P16-a0-g1-r0`：三个角色分别产生 `src.`、`src.`、`src/` 前缀，严格 ID 核验拒绝了结果。新协议在这 20 个正常且开启校验的任务中通过 20 个，完成率从本轮旧协议的 95% 到 100%。这是固定样本上的回归改善，不能推断所有任务都会改善。

160 次运行均返回完成，API 错误为 0；账本预留与记录调用数均为 480。服务返回 usage 合计 **310,948 token**，其中旧协议 154,255、新协议 156,693。预算日志和原始模型输出只保留本机，公开汇总由实际逐次记录生成，见 [results_v2.json](results_v2.json)。

所有含注入组仍为零成功，因此**本轮没有证据证明攻击成功率降低**。这批任务上一次已使用，属于已知任务回归，不是未见测试集；每条件仅 20 个固定格式提取任务，没有统计显著性或安全保证的结论。原文匹配仍不能判断来源陈述是否真实，主题标签也不在逐字结论核验范围内。

## 实际管线与回归

新版实际模型批量分析再次处理 24 条输入，清洗、去重及预设范围筛选后输出 21 条；21 篇学术笔记保留原始来源。三批均明确记录 `program-index-v2`，每批 5 条引用通过、0 条拒绝。结果见 [demo_summary_v2.json](demo_summary_v2.json)。数据库沿用之前的演示，因此累计分析运行数为 5，不是五次全新数据集。此演示的三个模型调用不计入上述 480 次对照请求。

联合检查 **71 项测试通过**：项目 04 原有选定检查 41 项、新增序号绑定/持久预算/锁/恢复检查 16 项，项目 01 文献模块 14 项。另通过新 Python 源码 Ruff 检查，以及 TypeScript/Vite 生产构建。旧 SQLAlchemy 接口仍有一条弃用提示。本次没有重复旧版的整套浏览器人工操作，前端改动的验证范围为类型检查和生产构建。

## 复现命令

安装项目 04 的锁定依赖后，在 `projects/multi-agent-security-research` 目录配置自己的模型服务，使用一个从未用过的输出目录：

```powershell
uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.evaluate run --corpus experiments/source_tracking/local-runs/corpus/corpus.jsonl --output experiments/source_tracking/local-runs/my-id --model deepseek-flash --offset 2 --cases 20 --repeats 1 --max-calls 240 --concurrency 2 --source-selection id
uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.evaluate run --corpus experiments/source_tracking/local-runs/corpus/corpus.jsonl --output experiments/source_tracking/local-runs/my-index --model deepseek-flash --offset 2 --cases 20 --repeats 1 --max-calls 240 --concurrency 2 --source-selection index
uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.demo --corpus experiments/source_tracking/local-runs/corpus/corpus.jsonl --output experiments/source_tracking/local-runs/my-demo.json
```

语料获取、`.env` 配置、源码位置、预算恢复规则及前端构建命令见 [README.md](README.md)。本次环境为 Windows、Python 3.11.9、Node.js 20.17.0、uv 0.13.5。语料 SHA-256 仍为 `7aa7b7033503d9c836637835d0d5a9f8787e35e70b2661c06c90aa909e1766bc`。

联合测试从课程根目录执行：

```powershell
uv run --frozen --project "projects/project-04-Intelligence Gathering" python -m pytest "projects/project-04-Intelligence Gathering/tests/test_source_grounding.py" "projects/project-04-Intelligence Gathering/tests/test_grounding_v2.py" "projects/project-04-Intelligence Gathering/tests/test_api_limits.py" "projects/project-04-Intelligence Gathering/tests/test_store_factory.py" projects/project-01-ai-researcher/coursework/test_arxiv_metadata.py -q
```

## 任务 01 的尝试

同期修复项目 01 的文献版本查询，直接运行原文献工具，真实获取 `2410.07283v1` 与 `2406.13352v1` 两篇元数据并验证返回版本。新增标准库独立入口，保留原工具接口；移除网页入口强制覆盖网络代理的代码。详见[项目 01 模块报告](../../../project-01-ai-researcher/coursework/README.md)。本机无 Docker，完整研究代理和容器实验仍未运行，不将模块运行称为完整框架复现。
