# 四项目论文证据交接流程

2026-11-18，针对写作前暴露的问题先优化，再执行。此入口串联四个项目中的独立模块，不代表四套完整自动研究平台已部署。

| 项目 | 本次完善 | 实际执行 |
| --- | --- | --- |
| 01 AI-Researcher | 批次每完成一篇立即回调保存，后续中断保留已取得的资料；CLI 保存 progress.json | 4 篇固定版本 arXiv 元数据实时请求、身份核对及逐篇保存 |
| 02 AI-Scientist-v2 | 新增独立 evidence_audit，核对计数、比率、条件完整性、预算与配对配置；输出解释边界 | 审核已有 results_v2.json 的两协议八组汇总，确认 160 次运行、480 次历史调用 |
| 03 DeepTutor | 引用模块延迟导入环境服务；损坏档案明确报错；原子写入；保存失败回滚内存；恢复时校正编号；识别畸形引用 | 使用原 CitationManager 保存 4 条引用并验证其标识 |
| 04 Intelligence Gathering | 新增只携带来源与已核验原文摘录的交接格式，不把未核验的模型主题或摘要传作证据 | 导出 4 条原文摘录及程序生成来源 ID |

## 运行

Python 3.11+，入口本身仅需标准库，不需要 Docker、CUDA 或模型密钥。从 `projects/multi-agent-security-research` 执行：

```powershell
python -m experiments.source_tracking.paper_pipeline --id 2410.07283v1 --id 2406.13352v1 --id 2503.18813v2 --id 2610.05640v1 --output experiments/source_tracking/local-runs/paper-evidence
```

输出必须是新目录。会生成逐篇元数据、实验审计、证据包、引用档案、引用检查及 manifest。摘要的原文匹配只验证可追溯性，不验证真实性或任务相关性。汇总审核不等于重新验证全部原始模型轨迹；不能把无攻击成功解释为防御效果已获证明。当前引用档案仍要求单进程写入，未增加跨进程锁。

本次实际运行完成：4 次 arXiv 请求，4 条引用有效，4 条摘录通过，新增模型调用 0。论文由当前写作助手基于该交接包、项目 02 的写作规范与项目 03 的研究分解流程撰写，不是完整 AI-Scientist 自动生成实验后产出的论文。

## 验证

项目 01/04 相关回归加交接测试共 92 项通过；DeepTutor 原有引用测试单独 4 项通过，合计 96 项。原 SQLAlchemy 弃用警告保留。新交接模块通过 Ruff E4/E9/F 检查。

从课程根目录运行交接测试：

```powershell
python -m pytest projects/multi-agent-security-research/experiments/source_tracking/test_paper_handoff.py projects/project-01-ai-researcher/coursework "projects/project-04-Intelligence Gathering/tests/test_evidence_export.py" -q
```

DeepTutor 原有四项引用测试可在项目 03 目录使用 `python -m pytest --confcutdir=tests/agents/research tests/agents/research/test_citation_manager.py -q` 独立执行，避免加载完整平台的根级测试环境。
