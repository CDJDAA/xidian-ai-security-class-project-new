# V1 多重比较敏感性检查

集合：`new800`；家族：`bsr_vs_mi`；共 24 个记录中的对照；α=0.05。

这是对已观察数据的事后敏感性检查，条件于当前模型和已有攻击种子，不是新实验或独立确认。每张图先平均种子，再按原生成 batch 聚类；没有把三个种子乘成三倍图片。

主结果是 Holm 校正后的近似 cluster-t p 值。原图片 bootstrap 区间与另算的 Bonferroni cluster-t 近似同时区间均保留在 JSON/CSV；它们不是 Holm/BH 区间。BH 仅作探索，其依赖条件未在本实验中验证。不拒绝零差异不等于证明等效或无差异。

| 目标 | 方法 A − B | ΔASR／百分点 | 原始 p | Holm p | BH p（探索） | Holm 拒绝零差异 | 状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20 | -0.92 | 0.4892 | 0.9784 | 0.5105 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20_fixed_step | -3.03 | 0.01212 | 0.06058 | 0.01454 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20 | -5.00 | 0.000869 | 0.007753 | 0.001227 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20_fixed_step | -7.11 | 1.107e-05 | 0.0001439 | 2.214e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40 | +4.78 | 5.798e-05 | 0.0006958 | 0.000107 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40_fixed_step | +2.41 | 0.05868 | 0.176 | 0.06401 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40 | +2.46 | 0.02906 | 0.1162 | 0.03321 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40_fixed_step | +0.09 | 0.9452 | 0.9784 | 0.9452 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80 | +9.47 | 1.229e-10 | 2.336e-09 | 4.918e-10 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80_fixed_step | +6.18 | 3.688e-07 | 5.163e-06 | 8.046e-07 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80 | +7.28 | 1.93e-08 | 3.088e-07 | 5.147e-08 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80_fixed_step | +3.99 | 0.0005204 | 0.005204 | 0.0008326 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20 | +4.47 | 0.0008614 | 0.007753 | 0.001227 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20_fixed_step | +4.07 | 0.0004639 | 0.005103 | 0.0007953 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20 | +3.85 | 0.002734 | 0.01914 | 0.003645 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20_fixed_step | +3.45 | 0.00558 | 0.03348 | 0.007048 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40 | +10.83 | 3.051e-10 | 5.187e-09 | 9.153e-10 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40_fixed_step | +13.22 | 5.944e-13 | 1.189e-11 | 2.853e-12 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40 | +8.84 | 2.154e-07 | 3.23e-06 | 5.168e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40_fixed_step | +11.23 | 2.665e-10 | 4.797e-09 | 9.137e-10 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80 | +16.49 | 4.42e-15 | 9.723e-14 | 3.536e-14 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80_fixed_step | +21.66 | 4.112e-20 | 9.869e-19 | 9.869e-19 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80 | +14.90 | 5.932e-15 | 1.246e-13 | 3.559e-14 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80_fixed_step | +20.07 | 3.7e-18 | 8.511e-17 | 4.44e-17 | 是 | ok |

只有一个有效 cluster 或 cluster 方差为零时不报告确定的 p 值；相关行保留在家族大小中。正差值表示 A 的 ASR 更高，拒绝零差异本身不表示差异方向为正。

完整条件、输入 SHA256、各对照有效图片数与 batch 数见 [JSON](multiplicity.json)；便于查看的表格见 [CSV](multiplicity.csv)。

该目录为新建分析输出；未修改原始结果或重新运行模型、攻击。
