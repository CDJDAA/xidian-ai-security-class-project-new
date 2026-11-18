# 论文图件

- `workflow.png`：作者依据项目职责绘制的概念图；上方模块排列不代表程序执行顺序，下方箭头表示三角色交接。
- `probe-matrix.png`：直接读取 `experiments/source_tracking/boundary-probe-20261118.json` 的 cases/outcomes/accepted 字段。每个单元仅表示一条摘录是否接纳，不能当作安全评分；星号标出通过但改变预期来源的案例。

生成方式：Python 3.11+、Matplotlib，执行本目录 `generate_figures.py`。本次使用 Matplotlib 3.11.2 与 Windows 宋体；其他系统需将脚本中的字体路径改为可用中文字体。数据没有平滑、归一化或合并，无误差线，因为这是确定性案例矩阵而非抽样估计。图均为本项目原创；没有复制第三方图件。
