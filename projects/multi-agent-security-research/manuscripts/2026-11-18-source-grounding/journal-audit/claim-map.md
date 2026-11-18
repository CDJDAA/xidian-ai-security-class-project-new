# 关键论点与证据定位

下表由 AI 整理，人工核实尚未完成。它覆盖本轮主要论点，不声称完成逐句完整审计。E 编号为稳定证据 ID，正文参考文献编号映射见 `revision-checks.json`。

| 论点 | 正文位置 | 证据与定位 | 性质与限制 |
| --- | --- | --- | --- |
| 正常有校验任务为 19/20 与 20/20 | 5.1 | E005，results_v2.json 两协议 attacked=false/guarded=true | 历史汇总，未重新审核全部轨迹 |
| 含注入基线也为零成功 | 5.2 | E005，两协议 attacked=true 的四组 | 不能据此推导防御收益 |
| 序号协议 token 增加约 1.58% | 5.2 | E005，total_tokens 154255 与 156693 | 描述性成本差异 |
| 来源固定时的受限输出不变量 | 3.3 命题 1 | E011 代码哈希关联 grounding.py；式（1）及归纳推导 | 条件推导，仅覆盖核验结论字段 |
| 重排共享摘录不能保持原来源 | 3.3 命题 2、5.7 | E011，cases/stale_common/outcomes | 有意违反固定快照假设 |
| 唯一摘录重排可触发拒绝 | 5.7 | E011，cases/stale_unique/outcomes | 不能外推至共享摘录 |
| 原文内指令与无关摘录均接纳 | 5.5 | E011，cases/instruction_quote、irrelevant_quote | 不估计模型服从概率 |
| 自由摘要标记在有校验链中消失 | 5.6 | E011，handoffs/summary_payload/marker_summary_by_role | 固定回声响应 |
| 主题标记跨三轮传递 | 5.6 | E011，handoffs/topic_payload/marker_topics_by_role | 说明通道存在，非真实攻击率 |
| 受限导出不传递未核验主题 | 5.6 | E011，evidence_export 字段 | 原始 sources 仍不可信 |
| CSV 局部测量改善 | 5.3 | E006，csv-benchmark-20261118.json | 包含 tracemalloc 开销 |
| 版本化映射及独立授权建议 | 6.2、6.3 | 上述反例及 E003/E004 的研究定位 | 设计建议，尚未实现完整系统 |

声明与作者资格不由上述实验推断。语言检查中的 POTENTIAL_OVERSTATEMENT 对应英文摘要的 guarantees 一词，此处描述待分析的局部保证及其限制，并非声称普遍有效；经 AI 复核保留原文，仍待作者核实。CONFIDENTIALITY_GATE_NOT_CHECKED 表示未登记人工政策审查，不能由自动检查代填。用户已明确要求更新公开项目。
