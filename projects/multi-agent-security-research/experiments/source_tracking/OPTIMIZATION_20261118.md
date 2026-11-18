# 任务 01 / 04：运行效率与恢复完整性优化

学号 / 姓名：26241215025 / 董俊逸。日期：2026-11-18。
基于 PR #5 的 `7c25929`，延续已完成的来源绑定、预算持久化和文献版本核验。

## 任务 01：减少重复文献请求

标准库入口 `coursework.arxiv_smoke` 在发出请求前校验整个批次，将 arXiv ID、abs/pdf 链接规范化后复用本批次成功的结果。保持输入顺序，每个输入仍有独立输出文件与状态；不同版本、未指定版本分别处理，失败不会进入缓存。缓存只在一次运行内有效，结果深复制，避免调用方修改影响其他记录。实际请求之间保持至少三秒的启动间隔；缓存命中不等待。

真实运行输入 `2410.07283v1`、对应 PDF 链接、再次输入同一 ID，三个结果均成功且版本及响应哈希一致。实际请求 **1 次**，后两个结果复用；原实现对三个输入会请求 3 次并固定等待两次。首个请求耗时 0.844 秒；后两次复用在毫秒精度下为 0。新增 `metadata_requests`、`reused_in_batch` 字段可区分请求和复用。公开记录见[文献实测汇总](../../../project-01-ai-researcher/coursework/optimization-results-20261118.json)。

## 任务 04：按需读取与离线恢复

- CSV 改为只解析所需行数，避免请求前 500 行却把整份文件转换成字典列表。零或负数上限直接返回空列表；保留 BOM、引号及逗号字段处理。
- 已完成全部计划任务时，校验记录与账本后直接重建汇总，不初始化模型客户端，不要求模型密钥，也不发送模型请求。
- 恢复时拒绝重复或未知任务 ID、与计划不符的任务身份、负数或超界计数、非有限耗时和非布尔结果，避免错误统计或跳过应执行任务。
- 每条完成记录写入后刷新到磁盘；汇总先写临时文件，再原子替换。预算账本缺失末尾换行时拒绝继续追加，防止拼接成损坏记录。

恢复不会自动删除损坏数据，也不会自动重试历史模型错误记录；保留既有保守预算语义。崩溃产生的残留锁仍需确认旧进程停止后手动处理。

## CSV 对照实测

Windows / Python 3.11.9，合成 CSV 100,000 行，取前 500 行，各运行三次。使用 `tracemalloc` 记录 Python 分配峰值；计时包含该测量开销，不代表整套系统端到端吞吐量。

| 指标 | 原整表读取 | 按需读取 |
| --- | ---: | ---: |
| 中位耗时（秒） | 1.250349 | 0.005745 |
| Python 峰值分配（字节） | 49,324,762 | 280,375 |
| 返回记录 | 500 | 500 |

两种方法返回值完全一致。脚本与[原始测量结果](csv-benchmark-20261118.json)随代码提交。测试使用的超长尾部 CSV 能验证读取在上限处停止，不仅比较返回列表长度。

## 验证结果

联合回归 **79 项通过**（原 71 项及本次新增 8 项），另扩展了已有恢复测试的异常记录与零客户端断言。Python 3.11.9；存在一条原有 SQLAlchemy 弃用警告。新增模块及修改的实验/文献入口通过 Ruff E4/E9/F 检查。

## 复现

在课程仓库根目录，使用已安装项目 04 依赖的 Python 3.11+：

```powershell
python -m pytest "projects/project-04-Intelligence Gathering/tests/test_source_grounding.py" "projects/project-04-Intelligence Gathering/tests/test_grounding_v2.py" "projects/project-04-Intelligence Gathering/tests/test_api_limits.py" "projects/project-04-Intelligence Gathering/tests/test_store_factory.py" "projects/project-04-Intelligence Gathering/tests/test_bounded_csv.py" projects/project-01-ai-researcher/coursework -q
cd projects/multi-agent-security-research
python -m experiments.source_tracking.benchmark_csv
cd ../project-01-ai-researcher
python -m coursework.arxiv_smoke --id 2410.07283v1 --id https://arxiv.org/pdf/2410.07283v1.pdf --id 2410.07283v1 --output coursework/local-runs/my-optimization
```

文献实测仅请求公开 arXiv 元数据。本次未重新运行真实模型攻击实验，历史 480 次调用结果仍见原报告；恢复行为通过可控模型替身测试，不能解释为新的攻击防御结果。
