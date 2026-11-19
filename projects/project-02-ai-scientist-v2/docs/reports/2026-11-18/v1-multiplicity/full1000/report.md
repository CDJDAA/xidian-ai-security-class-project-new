# V1 多重比较敏感性检查

集合：`full1000`；家族：`bsr_vs_mi`；共 24 个记录中的对照；α=0.05。

这是对已观察数据的事后敏感性检查，条件于当前模型和已有攻击种子，不是新实验或独立确认。每张图先平均种子，再按原生成 batch 聚类；没有把三个种子乘成三倍图片。

主结果是 Holm 校正后的近似 cluster-t p 值。原图片 bootstrap 区间与另算的 Bonferroni cluster-t 近似同时区间均保留在 JSON/CSV；它们不是 Holm/BH 区间。BH 仅作探索，其依赖条件未在本实验中验证。不拒绝零差异不等于证明等效或无差异。

| 目标 | 方法 A − B | ΔASR／百分点 | 原始 p | Holm p | BH p（探索） | Holm 拒绝零差异 | 状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20 | -1.16 | 0.3107 | 0.6214 | 0.3242 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20_fixed_step | -2.94 | 0.005 | 0.025 | 0.006 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20 | -4.94 | 0.0001407 | 0.0009848 | 0.0001876 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20_fixed_step | -6.72 | 1.234e-06 | 1.604e-05 | 2.467e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40 | +4.80 | 4.357e-06 | 5.228e-05 | 8.044e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40_fixed_step | +2.17 | 0.04029 | 0.1209 | 0.04395 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40 | +2.52 | 0.01302 | 0.0521 | 0.01489 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40_fixed_step | -0.11 | 0.9223 | 0.9223 | 0.9223 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80 | +9.49 | 4.991e-13 | 8.87e-12 | 1.497e-12 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80_fixed_step | +6.55 | 5.721e-09 | 8.009e-08 | 1.248e-08 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80 | +7.25 | 3.584e-10 | 5.376e-09 | 8.602e-10 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80_fixed_step | +4.31 | 3.07e-05 | 0.0002763 | 4.605e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20 | +5.30 | 9.223e-06 | 0.0001015 | 1.581e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20_fixed_step | +4.24 | 2.431e-05 | 0.0002431 | 3.889e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20 | +4.66 | 3.291e-05 | 0.0002763 | 4.646e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20_fixed_step | +3.60 | 0.0006959 | 0.004176 | 0.0008791 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40 | +11.62 | 5.762e-14 | 1.095e-12 | 2.305e-13 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40_fixed_step | +13.42 | 1.017e-15 | 2.033e-14 | 4.88e-15 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40 | +9.57 | 2.426e-10 | 3.882e-09 | 6.47e-10 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40_fixed_step | +11.37 | 4.928e-13 | 8.87e-12 | 1.497e-12 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80 | +16.81 | 4.649e-19 | 1.023e-17 | 3.72e-18 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80_fixed_step | +21.15 | 1.28e-22 | 3.072e-21 | 3.072e-21 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80 | +15.18 | 8.514e-19 | 1.788e-17 | 5.108e-18 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80_fixed_step | +19.53 | 1.107e-20 | 2.545e-19 | 1.328e-19 | 是 | ok |

只有一个有效 cluster 或 cluster 方差为零时不报告确定的 p 值；相关行保留在家族大小中。正差值表示 A 的 ASR 更高，拒绝零差异本身不表示差异方向为正。

完整条件、输入 SHA256、各对照有效图片数与 batch 数见 [JSON](multiplicity.json)；便于查看的表格见 [CSV](multiplicity.csv)。

该目录为新建分析输出；未修改原始结果或重新运行模型、攻击。
