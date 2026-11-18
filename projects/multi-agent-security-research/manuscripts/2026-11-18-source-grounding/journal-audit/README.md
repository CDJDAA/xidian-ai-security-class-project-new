# 研究深化稿的核对记录

本目录记录结构化检查，不是投稿认证。11 条来源的人工核实状态均为 unverified；AI 核对公开元数据和本地记录不代替作者审查。关键论点见 [claim-map.md](claim-map.md)。

在仓库根目录使用 Python 3.11+：

```powershell
$skill = '.agents/skills/scientific-writing/scripts'
$audit = 'projects/multi-agent-security-research/manuscripts/2026-11-18-source-grounding/journal-audit'
python "$skill/check_consistency.py" "$audit/consistency_manifest.json"
python "$skill/check_references.py" "$audit/source_manifest.json"
python "$skill/validate_manifest.py" "$audit/source_manifest.json" --kind source
python "$skill/lint_manuscript.py" "$audit/../paper.md"
```

一致性登记为 50 项数值、3 类方法和 6 类结果。独立核对历史表 8 行、脚本交接表 4 行及 4 个代码文件哈希，结果见 revision-checks.json。E 证据编号保持稳定，正文参考文献按首次出现重新编号，映射亦在该文件中。

语言检查有两项提示：未登记人工政策审查，以及英文摘要使用 guarantees 一词。后者指本文研究的局部保证与限制，AI 复核未发现普遍有效性主张，保留原文并待作者核实。引用检查仅检查语法及重复标识，不解析网络或自动验证语义支持。完整逐论点人工审计及作者审核尚未完成，submission_ready 为 false。

本轮 28 项代码回归实际通过；它们与此前 96 项有重叠。定向机制实验和真实模型历史实验分别记录，不混合分母。
