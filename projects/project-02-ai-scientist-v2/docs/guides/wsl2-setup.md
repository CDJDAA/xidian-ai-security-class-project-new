# WSL2 开发与运行指南

本文说明如何安装、配置、验证与运行，实际测试结果另见[部署验证报告](../reports/2026-11-17/deployment.md)。项目 02 是批处理 CLI，不需要启动网页服务。

## 1. 进入环境

以能够正常启动的 WSL2 Ubuntu 为前提。Windows PowerShell：

```powershell
wsl -d Ubuntu --cd ~
```

以下命令在 **Ubuntu Bash** 执行，仓库路径按自己的机器调整：

```bash
cd "$HOME/projects/xidian-ai-security-class-project-new/projects/project-02-ai-scientist-v2"
export PATH="$HOME/.local/bin:$PATH"
nvidia-smi
```

代码和 `.venv` 放在 Linux 文件系统中。CUDA 使用 Windows 驱动映射，不在 WSL 另装 Linux NVIDIA 显示驱动。参见 [NVIDIA WSL 指南](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)。WSL2 需要 Windows hypervisor；要求关闭 Hyper-V 的游戏设置可能影响它启动。

## 2. 首次安装

已配置好的机器无需重新创建 `.venv`。首次安装时，准备 Linux uv，然后使用本项目已验证的 Python / PyTorch 组合：

```bash
uv venv --python 3.11
uv pip install 'torch==2.10.0' 'torchvision==0.25.0' \
  --index-url https://download.pytorch.org/whl/cu126
uv pip install -r requirements-course.txt
uv pip check
sudo apt-get update
sudo apt-get install --no-install-recommends poppler-utils chktex
```

轮子需与实际 GPU 和驱动兼容，安装后必须验证计算，不能只看 `nvidia-smi`。版本依据见 [PyTorch 官方版本表](https://pytorch.org/get-started/previous-versions/)。完整论文生成另需完整 TeX 环境；Poppler 和 chktex 不等于安装了 pdflatex。

## 3. 配置模型

填好的私有配置保存在仓库外，模板在 [configs/course.env.example](../../configs/course.env.example)。以下复制命令保留已有配置：

```bash
install -m 700 -d "$HOME/.config/ai-scientist-v2"
cp -n configs/course.env.example "$HOME/.config/ai-scientist-v2/course.env"
chmod 600 "$HOME/.config/ai-scientist-v2/course.env"
nano "$HOME/.config/ai-scientist-v2/course.env"
```

在本机填写 `DEEPSEEK_API_KEY`。默认地址为 `https://api.deepseek.com/v1`、模型为 `deepseek-flash`；运行器从私有文件加载变量，不需要把 Key 放进源码或 shell 历史。

客户端的凭据优先级为 `DEEPSEEK_API_KEY` → `OPENAI_API_KEY`；地址优先级为 `DEEPSEEK_BASE_URL` → `OPENAI_BASE_URL`。可通过 `--env-file` 指定其他私有配置文件。不同模型的文本、工具与图像能力应分别验证。

## 4. 离线检查

```bash
.venv/bin/python course_tools/run_course.py preflight
.venv/bin/python course_tools/check_environment.py \
  --ideas ai_scientist/ideas/course_transfer_budget.json
.venv/bin/python -m pytest tests/test_course_model_compat.py tests/test_course_runner.py -q
.venv/bin/python launch_scientist_bfts.py --help
.venv/bin/python ai_scientist/perform_ideation_temp_free.py --help
```

`preflight` 只报告配置、idea 和是否有凭据，不发送模型请求。环境检查器验证共享 idea schema，并在 GPU 与项目 Interpreter 子进程中执行已审查的小型 Linear 程序；测试使用 stub、禁止联网。

## 5. 生成课程候选

默认使用[课程主题](../../ai_scientist/ideas/course_transfer_budget.md)和[本地论文阅读记录](../research/transfer-attack-budget.md)生成 1 个候选，不覆盖人工整理的候选输入：

```bash
.venv/bin/python course_tools/run_course.py ideate --literature local --timeout 120
```

该命令会调用模型。原始结果写在 `experiments/course_ideate_<时间>/workshop.json`，来源记录写在同目录 `provenance.json`；必须非空且通过 schema 才算成功。它使用已有论文证据，不代表完成外部查新。

需要上游 Semantic Scholar 检索时显式选择，并保留总超时：

```bash
.venv/bin/python course_tools/run_course.py ideate --literature semantic-scholar --timeout 180
```

限流、超时和空输出应记为失败。完成后人工复核候选，将值得提交的原始 JSON 和来源记录复制到 `docs/reports/<日期>/`，在报告中注明是否经过人工修订；原始运行目录继续由 Git 忽略。

## 6. 后续实验

先阅读[研究方案](../research/transfer-attack-budget.md)，确认数据划分、预算和指标，再在受控实验环境使用：

```bash
.venv/bin/python course_tools/run_course.py experiment --idea-idx 0 --timeout 600
```

课程运行器将 [course_smoke.yaml](../../configs/course_smoke.yaml) 显式传给树搜索 API，使用独立运行目录；不沿用上游 launcher 的默认 Bedrock 配置，也不自动进入论文写作阶段。

该模式会执行模型生成的代码。上游 Interpreter 的子进程与超时不提供文件/网络隔离，WSL 默认可访问宿主盘；完整实验需受控容器或独立实验环境。单 worker、各阶段 1 次和超时可以限制规模，但不构成总 API 费用硬上限。

部分上游调用不透传 YAML 的 `max_tokens`。DeepSeek backend 对缺失值默认 4096，显式值仍保留；不能将 YAML 数字当作全部调用的硬 cap。上游 token tracker 没有 Flash 价格表，非思考 token 细节也可能未完整统计，实际用量与账单以供应商为准。

## 7. 日常开发

在 VS Code 的 WSL 窗口编辑 Linux 副本，Python 解释器选择本项目 `.venv/bin/python`。Windows 和 WSL 副本不自动同步；提交前检查差异，使用 Git 管理代码。

目录职责与提交范围见[文档导航](../README.md)。复用操作方法更新本指南；某台机器的版本、测试数量、失败原因与执行结果写入对应日期的报告。
