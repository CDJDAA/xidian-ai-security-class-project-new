# 项目 01：文献模块最小运行

学号 / 姓名：26241215025 / 董俊逸。日期：2026-11-01。

本次完成 AI-Researcher 参考文献元数据模块的小规模真实运行，验证了两篇论文的固定版本获取、来源记录和错误处理。

## 流程和修改

上游流程为：参考文献 → 文献/代码调查 → 研究构思 → 编码计划 → 容器实验 → 结果分析 → 论文写作。本次验证参考文献入口 `get_arxiv_paper_meta`。

旧实现把 `2410.07283v1` 的版本后缀删除后再查询，因此不能保证获取用户指定的版本。新实现保留现代及旧式 arXiv ID，使用固定 HTTPS API，并核对返回的论文和版本。保留调用方的字典/None 返回约定、原有日期类型及元数据字段；额外记录请求标识、获取时间和响应 SHA-256。

将最小传输及解析逻辑提取到 `research_agent/arxiv_metadata.py`，原来的工具函数调用该模块。独立入口按文件路径装载原工具，避免仅验证此函数时初始化整个研究框架。新入口仅依赖 Python 标准库，每次最多三篇，设置请求超时，两次查询之间等待三秒，失败返回非零退出码。

另修复网页入口无条件覆盖用户代理为开发者机器地址的问题，现继承用户自己的环境配置。

## 运行

从课程仓库根目录执行 PowerShell：

```powershell
cd projects/project-01-ai-researcher
uv run --no-project --python 3.11 python -m coursework.arxiv_smoke --id 2410.07283v1 --id 2406.13352v1 --output coursework/local-runs/my-attempt
uv run --no-project --python 3.11 --with pytest python -m pytest coursework/test_arxiv_metadata.py -q
```

`--no-project` 用于这个标准库模块，避免安装完整 AI-Researcher 的浏览器、模型及容器依赖；完整项目仍按上一级 README 安装。输出目录必须为新目录，避免覆盖既有证据。真实元数据只存于忽略的 `local-runs/`，公开汇总见 [results.json](results.json)。

## 实际结果

Windows / Python 3.11.9。通过原 `paper_search.py` 函数真实查询并成功返回：

| 请求与实际返回的 ID | 标题 |
| --- | --- |
| `2410.07283v1` | Prompt Infection: LLM-to-LLM Prompt Injection within Multi-Agent Systems |
| `2406.13352v1` | AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses for LLM Agents |

两条记录均成功保留 v1，完成返回版本核对并保存实际响应的 SHA-256。文献获取通过 arXiv API 完成。

新增测试覆盖版本保留、旧式编号、伪造域名、非法输入、返回错误论文/版本、超时参数及原函数错误返回约定；具体合并验证计数见项目 04 的本次报告。

## 版本与来源

课程基线 `6ec2ede98caf233a4168b9da8330a340e2517699`，课程记录的上游提交 `f9a6f8480860c193afff600eeffe3defcee8a978`。保留原作者说明及现有许可信息。本次 API 参数与 Atom 格式参考 [arXiv 官方 API 手册](https://info.arxiv.org/help/api/user-manual.html)。
