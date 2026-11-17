# 项目 02 文档导航

文档按用途组织：操作方法放指南，研究问题放方案，本次执行的证据放带日期的报告。

| 需要了解的内容 | 入口 |
| --- | --- |
| 如何在 WSL2 安装、配置和运行 | [WSL2 开发指南](guides/wsl2-setup.md) |
| 课程要研究什么、如何公平评价 | [迁移攻击预算与多样性方案](research/transfer-attack-budget.md) |
| 2026-11-17 实际完成了什么 | [部署验证报告](reports/2026-11-17/deployment.md) |
| 当日模型原始输出及来源 | [候选 JSON](reports/2026-11-17/ideation.json) · [来源记录](reports/2026-11-17/ideation.provenance.json) |
| 当日可公开的环境与测试摘要 | [验证摘要](reports/2026-11-17/verification.json) |

## 目录职责

```text
project-02-ai-scientist-v2/
├── README.md                       # 项目入口和快速导航
├── COURSE.md                       # 课程目标与交付要求
├── ai_scientist/                    # 上游核心实现与模型适配
│   └── ideas/
│       ├── course_transfer_budget.md    # 稳定的课程构思输入
│       └── course_transfer_budget.json  # 人工整理的候选输入
├── configs/
│   ├── course_smoke.yaml           # 可复用运行配置
│   └── course.env.example          # 无凭据环境变量模板
├── course_tools/                   # 课程检查器与运行器
├── tests/                          # 自动化验证
├── docs/
│   ├── guides/                     # 持续维护的安装、操作说明
│   ├── research/                   # 研究动机、协议和评价设计
│   └── reports/
│       └── 2026-11-17/              # 当日执行结果与精选证据
├── experiments/                    # 本机原始运行产物，Git 忽略
└── .venv/                          # 本机依赖环境，Git 忽略
```

新增一次运行时，新建对应日期的报告目录；保留旧报告的验证条件与结论。改进安装方法时更新 `guides/`，修改研究假设时更新 `research/`，不要把三类内容混写在同一文件里。

`ai_scientist/ideas/` 保留程序会读取的输入。模型生成的原始 JSON 放在当日报告旁，并与 provenance 一起保存；不要覆盖人工整理的候选来混淆来源。未整理的大量日志、缓存、模型权重继续留在 Git 忽略的运行目录中。

PR 提交核心代码、配置模板、测试、指南和当日精选证据；真实凭据保存在仓库外的用户配置目录。已有上游目录和入口保持其职责，避免仅为目录外观大幅重命名源码。
