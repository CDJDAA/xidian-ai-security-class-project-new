# 多智能体研究协作中的程序绑定来源与证据核验

董俊逸。2026 年 11 月 18 日通用期刊规范修订稿，保留中文正文并补充英文题名与摘要。尚待作者核实，不是特定期刊投稿定稿。

## 交付材料

| 文件 | 用途 |
| --- | --- |
| [paper.md](paper.md) | 可直接浏览的论文正文 |
| [paper.docx](paper.docx) | 可编辑 Word，9 页，已逐页检查 |
| [REVISION_NOTES.md](REVISION_NOTES.md) | 本轮修订内容与待确认事项 |
| [journal-audit](journal-audit/README.md) | 来源登记、数值一致性和引用格式检查 |
| [validation.json](validation.json) | 本轮编辑核对及此前模块执行范围 |
| [artifact-manifest.json](artifact-manifest.json) | 文件 SHA-256 与字节数 |

论文包括引言、材料与方法、结果、讨论、结论、声明、8 条参考文献和工作流补充说明。新增 [scientific-writing 技能](../../../../.agents/skills/scientific-writing/SKILL.md)及[来源许可说明](../../../../.agents/skills/scientific-writing/PROVENANCE.md)，采用通用结构，不声称遵循任何期刊官方模板。

## 与四个任务的关系

- 任务 01：文献版本查询、批次去重和逐篇检查点。
- 任务 02：写作前的实验计数、比例和配对配置审核。
- 任务 03：引用编号、损坏档案保护、可靠保存及引用检查。
- 任务 04：来源绑定、摘录核验、证据导出和运行恢复。

模块代码基线为 `79a53db26c9ae9cd3a6b383bd0ea89754e9544af`。复现命令见[四项目证据交接流程](../../experiments/source_tracking/PAPER_WORKFLOW.md)，性能数据见[优化报告](../../experiments/source_tracking/OPTIMIZATION_20261118.md)。此前相关代码检查共 96 项通过，实际取得并核对 4 篇固定版本文献；本轮编辑没有重跑这些代码测试。

## 证据与运行范围

160 次三角色运行、480 次模型调用来自 2026 年 11 月 1 日历史汇总，本次未重跑。四项目交接实际执行独立模块，并非四套完整自治平台。引用存在性与字面匹配不等于事实、语义或行为安全。当前缺少人工逐项来源核实和完整逐论点审核，稿件不标记为可直接投稿。

这里提交课程论文、公开验证汇总和获 MIT 授权的写作技能，不包含模型密钥、本机路径或第三方论文全文。
