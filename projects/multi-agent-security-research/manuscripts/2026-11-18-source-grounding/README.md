# 多智能体研究协作中的来源约束及其安全边界

董俊逸。2026 年 11 月 18 日研究深化稿：中文正文、英文题名与摘要，18 页，2 幅图、5 张表、11 条参考文献。当前为待作者核实的草稿，未指定投稿期刊。

## 阅读与复现

| 文件 | 用途 |
| --- | --- |
| [paper.md](paper.md) | 在线阅读全文及图表 |
| [paper.docx](paper.docx) | 可编辑 Word，18 页，已逐页检查 |
| [REVISION_NOTES.md](REVISION_NOTES.md) | 相比上一稿的研究深化内容 |
| [边界实验](../../experiments/source_tracking/BOUNDARY_PROBES.md) | 输入、逐轮输出与复现命令 |
| [关键论点与证据](journal-audit/claim-map.md) | 主要结论对应的数据与限制 |
| [本地核对记录](journal-audit/README.md) | 数字、参考文献及来源登记检查 |
| [图件及生成代码](figures/README.md) | 原创示意图与确定性接纳矩阵 |
| [validation.json](validation.json) | 历史与本轮验证范围 |
| [artifact-manifest.json](artifact-manifest.json) | 文件 SHA-256 与字节数 |

## 研究深化

论文建立来源可追溯性、任务相关性和行为授权的分层定义，给出接纳公式、受限交接不变量及跨重排反例。新增 18 个机制案例和 6 条脚本化三角色链，定位原文内指令、未核验主题以及共享摘录重排的边界，提出版本化映射、逐字段状态和独立授权的设计要求，并给出预算一致的后续评测方案。

使用 [scientific-writing](../../../../.agents/skills/scientific-writing/SKILL.md)，固定版本与 MIT 许可见[来源说明](../../../../.agents/skills/scientific-writing/PROVENANCE.md)。技能引用保留在参考文献中。

## 四项目与证据范围

任务 01 提供文献版本查询和检查点；任务 02 提供汇总审核；任务 03 提供引用登记及可靠保存；任务 04 提供来源绑定与摘录核验。[四项目流程](../../experiments/source_tracking/PAPER_WORKFLOW.md)代码基线为 `79a53db`，此前相关测试 96 项通过。本轮边界实验代码与数据为 `3006475`，实际重跑相关测试 28 项，两者存在重叠，不累加。

历史 160 次三角色运行、480 次模型调用没有重跑。新增 36 次核验函数求值与 18 次脚本角色响应不是模型调用，也不是随机攻击样本。新结果不证明通用防御有效，未运行四套完整自治平台。作者单位、贡献、资助与利益冲突等仍待确认。
