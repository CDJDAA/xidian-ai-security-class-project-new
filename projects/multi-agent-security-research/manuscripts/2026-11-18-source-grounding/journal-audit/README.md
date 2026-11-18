# 本轮期刊规范修订核对

本目录记录结构化编辑检查，不是投稿认证。`source_manifest.json` 中 8 条来源的人工核实状态全部保留为 `unverified`；AI 已核对的公开元数据不能代填人工审核。

从仓库根目录使用 Python 3.11 或更新版本执行：

```powershell
$skill = '.agents/skills/scientific-writing/scripts'
$audit = 'projects/multi-agent-security-research/manuscripts/2026-11-18-source-grounding/journal-audit'
python "$skill/check_consistency.py" "$audit/consistency_manifest.json"
python "$skill/check_references.py" "$audit/source_manifest.json"
python "$skill/validate_manifest.py" "$audit/source_manifest.json" --kind source
python "$skill/lint_manuscript.py" "$audit/../paper.md"
```

一致性登记包含 37 项数值、2 类方法和 4 类结果；检查的是已登记项目的内部一致性。`revision-checks.json` 另记录正文表格与历史 JSON 的比对，以及引入技能与上游的文件一致性。参考文献检查仅验证本地标识语法和重复项，不访问网络，也不证明来源支持相应论点。

语言检查保留 `CONFIDENTIALITY_GATE_NOT_CHECKED` 提示：未提供人工政策审核记录，且检查器主要使用英文规则。用户已明确要求更新公开项目；此提示不等于新增发布审批要求。中文内容经过 AI 编辑复核，仍待作者审定。

未执行完整逐论点人工审计或作者资格审核。`submission_ready` 保持 `false`。不得将上述局部通过状态表述为全部科学内容已核实或满足任何目标期刊的全部要求。
