# 2026-11-17 部署验证报告

本报告记录当天实际执行结果，安装与运行方法见 [WSL2 开发指南](../../guides/wsl2-setup.md)，研究目标见[课程方案](../../research/transfer-attack-budget.md)。

## 验证范围

完成项目 02 独立环境、CLI、CUDA 运算、上游 Interpreter、小范围模型适配测试及真实 Flash 构思验证。没有进行正式 CIFAR-10 对比实验或完整论文生成。

| 检查项 | 当天实际结果 |
| --- | --- |
| 平台 | Ubuntu 26.04.1 / WSL2，用户 `zst` |
| Linux 工作区 | `/home/zst/projects/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2` |
| Python | 独立 `.venv`，3.11.18 |
| GPU | GTX 1660 Ti，6 GB，计算能力 7.5；轮子包含 `sm_75` |
| PyTorch | 2.10.0+cu126；TorchVision 0.25.0+cu126，CUDA runtime 12.6 |
| GPU 运算 | 张量反传、优化器更新和有限值检查通过 |
| 项目 Interpreter | 子进程内审查过的 Linear GPU 反传程序通过，原始检查耗时约 1.803 秒 |
| Python 依赖 | `uv pip check` 通过 |
| PDF 工具 | Poppler 26.01.0、chktex 1.7.9；没有完整 pdflatex |
| 上游入口 | 实验入口和构思入口的 `--help` 均通过，无导入错误 |
| 课程配置 | 通过上游结构化配置校验，单 worker、四个阶段各 1 次，模型角色均为 `deepseek-flash` |
| 自动化测试 | 22 passed、12 subtests passed，覆盖模型/工具/图像请求结构、缺失凭据保护、真实子进程超时及本地文献输出结构 |
| 模型小请求 | 指定端点 `https://api.deepseek.com/v1`，API 实际返回 `deepseek-flash`，回答 OK；输入 9 / 输出 1 token |
| 本地文献构思 | 真实生成 1 个候选，通过 schema；该请求输入 3714 / 输出 2472 token |

没有在 WSL 安装 Linux NVIDIA 显示驱动。依赖环境只安装在 Linux 副本，课程文件与适配代码保存在 Windows 仓库并同步到 Linux。项目 03/04 服务保持运行；未提交或推送代码。

## 可公开的证据

- [验证摘要](verification.json)：精选环境、GPU、配置、API 和测试记录，不包含 Key 或完整请求日志。
- [Flash 原始候选](ideation.json)：保留模型原始输出，未静默改写。
- [候选来源记录](ideation.provenance.json)：模型、文献模式及该请求返回的 token 数。
- [人工整理的三个候选](../../../ai_scientist/ideas/course_transfer_budget.json)：程序输入，推荐 index 0；与模型原始输出分开保存。

原始成功运行目录为 `experiments/course_ideate_2026-11-17_19-37-05-131928/`，由 Git 忽略。PR 仅保存上面经过筛选的证据。

## 遇到的问题与处理

1. 上游默认实验模型为 Bedrock Claude，已有 DeepSeek 路由针对旧模型名。补齐当前 Flash 文本、树搜索和看图消息的适配，移除不支持的 n/seed，使用非思考请求格式；离线测试覆盖了这些请求结构。
2. 批量接口的外层 token-tracking 装饰器与其 tuple 返回值不匹配，已修复。
3. 上游 Semantic Scholar 检索持续返回 HTTP 429，已由 180 秒进程组超时终止，该次**未生成成功**。随后根据五篇本地论文阅读记录，通过本地文献模式生成了候选。

没有把限流失败记作外部查新通过，也没有把 stub 测试当作真实视觉能力验证。

## 人工复核与局限

Flash 候选与预定预算、数据划分和目标隔离协议基本一致。其摘要中的“固定更新步长”应按实验清单理解为各比较组固定迭代数，实际步长为 `alpha=epsilon/T`；“本发明”等措辞不代表已具备发表或专利级新颖性。正式执行以[人工整理的冻结协议](../../research/transfer-attack-budget.md)为准。

- 外部查新未完成；不能保证研究问题或结论在发表意义上新颖。
- 正式 CIFAR-10 训练、迁移 ASR、统计对比和论文生成没有执行，当前没有相应研究结果。
- 看图接口只验证了请求结构；没有真实视觉任务结果。
- 上游 Interpreter 不是文件/网络沙箱；完整自动代码实验需另行准备受控执行环境。
- 没有完整 TeX 环境，不能声称通过论文 PDF 生成验收。
- token tracker 的未知模型费用 0 不表示免费，账单以供应商为准。

后续执行应新增当日报告，并保留本报告的验证条件和结论。
