# 人工智能安全课程基础项目

班级仓库：[CDJDAA/xidian-ai-security-class-project-new](https://github.com/CDJDAA/xidian-ai-security-class-project-new)。

本课程目录包含四个基础项目，供同学选择开展源码阅读、复现、功能扩展与安全分析。前三个来自 GitHub 上游源码，第四个为本地整理的“Intelligence Gathering”。各项目独立安装和运行，共用课程仓库的分支与提交规范。

## 项目选择

| 编号 | 项目 | 主要内容 | 项目说明 | 课程任务 |
| --- | --- | --- | --- | --- |
| 01 | AI-Researcher（HKUDS） | 自动研究流程与研究代理 | [README](projects/project-01-ai-researcher/README.md) | [COURSE](projects/project-01-ai-researcher/COURSE.md) |
| 02 | AI-Scientist-v2（SakanaAI） | 研究想法生成、实验树搜索与论文生成 | [README](projects/project-02-ai-scientist-v2/README.md) | [COURSE](projects/project-02-ai-scientist-v2/COURSE.md) |
| 03 | DeepTutor（HKUDS） | 智能辅导、知识问答与学习代理 | [README](projects/project-03-deeptutor/README.md) | [COURSE](projects/project-03-deeptutor/COURSE.md) |
| 04 | Intelligence Gathering | 多源采集、内容分析、知识库归档与研究想法生成 | [README](projects/project-04-Intelligence%20Gathering/README.md) | [COURSE](projects/project-04-Intelligence%20Gathering/COURSE.md) |

## 目录结构

```text
xidian-ai-security-class-project/
├── README.md
├── .gitignore
└── projects/
    ├── project-01-ai-researcher/
    ├── project-02-ai-scientist-v2/
    ├── project-03-deeptutor/
    └── project-04-Intelligence Gathering/
```

每个项目都包含中文使用 README.md 和课程任务 COURSE.md。README 按环境准备、依赖安装、模型配置、启动、首次演示与排错组织；整理前的说明保存在各项目 README.original.md。各自的依赖、示例与原始许可文件保存在对应目录内。

## 开始使用

1. 选择一个项目，阅读其 README 与 COURSE.md，再进入该项目目录执行安装和启动命令。
2. 四个项目分别创建环境，按各自要求配置模型服务与 API Key。
3. 先运行小规模示例，记录环境和结果，再修改代码；本次目录整理不代表已完成运行验证。
4. Intelligence Gathering适合从本地资料处理与知识归档流程入手；基础启动见 [项目 04 快速开始](projects/project-04-Intelligence%20Gathering/README.md#快速开始)。
5. AI-Scientist-v2 上游要求 Linux、NVIDIA GPU、CUDA 和 PyTorch，并会执行模型生成代码，应遵循其隔离运行说明。

项目 02 与项目 04 是独立项目。Intelligence Gathering的可选实验适配层要求特定接口，不能因两者放在同一课程目录就认为已经互相兼容。

## 同学分支与教师查看修改

班级仓库采用下述协作流程；同仓库推送需要教师先添加同学为协作者，并由同学接受邀请。课程推荐同仓库个人分支：同学仅在自己的分支开发，教师可直接查看各分支的已推送提交。若教师改用 Fork 方式，同学还需向课程仓库建立 PR，教师才能集中审阅。

首次下载（同仓库协作者方式）：

```bash
git clone https://github.com/CDJDAA/xidian-ai-security-class-project-new.git
cd xidian-ai-security-class-project-new
```

下载包含上游示例和演示资源，体积较大。仅希望取得当前版本时可在 clone 中添加 `--depth 1`。

确认工作区没有未提交修改后，在课程仓库根目录执行（将学号与项目编号替换为实际值）：

```bash
git switch main
git pull --ff-only
git switch -c students/YOUR_STUDENT_ID/project-04
```

每完成一个小功能或修复一个问题，在课程仓库根目录提交：

```bash
git add "projects/project-04-Intelligence Gathering"
git diff --cached
git commit -m "项目04：说明本次具体改动"
git push -u origin students/YOUR_STUDENT_ID/project-04
```

其他项目替换目录及编号即可。不要在项目子目录初始化新的 Git 仓库，不要修改他人分支或强制推送。

教师在 GitHub 的分支下拉框选择学生分支，通过 Commits 查看逐次记录；在 PR 的 Files changed 中查看相对基础版本的改动。main 页面只显示主分支历史。Git 记录已提交的修改，教师只能看到已推送到远程的内容，无法看到同学仅在电脑上保存的改动。


## 来源、许可与整理状态

前三个项目的使用 README 记录整理时的上游提交编号，项目 04 来自本地教学版；保留原作者版权，不用课程说明替代上游许可。

- AI-Researcher 本次下载根目录没有独立 LICENSE 文件，使用与分发前需核实上游授权。
- AI-Scientist-v2 和 DeepTutor 保留各自 LICENSE。
- Intelligence Gathering基于 MediaCrawler 二次开发，遵循项目内的非商业学习许可证；每位同学独立配置自己的 API。

AI-Researcher 有 182 个文件名为兼容 Windows 做了字符替换，当前目录未保留名称对照文件，可对照原始压缩包检查名称。文件内容未因此修改；按原名访问资源的代码可能需要适配。原始压缩包和上游 Git 元数据保存在本机课程目录旁的“课程项目下载备份”，不会随课程源码自动发布。

Intelligence Gathering以源码副本加入，已排除本地密钥、虚拟环境、生成数据、知识库、日志和旧发布目录；原始本地项目保留。本仓库发布课程源码与使用说明，尚未统一安装依赖或完成四个项目的运行验收。上传前已将发现的上游示例硬编码密钥改为环境变量读取或占位符，运行时请自行配置凭据。
## 没有协作者权限时：Fork 交作业

1. 点击本仓库右上角 Fork，在自己的账号下建立副本。
2. 克隆自己的副本，创建 `students/学号/project-编号` 分支，分次 commit 并 push。
3. 在个人仓库点击 Contribute → Open pull request，目标选择 `CDJDAA/xidian-ai-security-class-project-new` 的 `main`，来源选择自己的作业分支。
4. 教师在本仓库 Pull requests 中查看 Commits 和 Files changed。仅 Fork 或仅向个人仓库 push，不会自动出现在教师仓库的提交记录中。

## 教师审阅入口

- [学生分支](https://github.com/CDJDAA/xidian-ai-security-class-project-new/branches)：同仓库方式下查看学生已推送分支。
- [作业 PR](https://github.com/CDJDAA/xidian-ai-security-class-project-new/pulls)：集中查看提交说明、逐次改动并反馈。
- [主分支历史](https://github.com/CDJDAA/xidian-ai-security-class-project-new/commits/main/)：课程基础版本历史，不等同于所有学生分支历史。

本说明不代表协作者或分支保护已自动配置；教师需在 Settings 中完成相应设置后开放班级共同写入。
