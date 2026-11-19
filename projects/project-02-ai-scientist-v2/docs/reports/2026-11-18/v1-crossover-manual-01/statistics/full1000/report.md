# V1 多重比较敏感性检查

集合：`full1000`；家族：`all_six_pairwise_contrasts`；共 84 个记录中的对照；α=0.05。

这是对已观察数据的事后敏感性检查，条件于当前模型和已有攻击种子，不是新实验或独立确认。每张图先平均种子，再按原生成 batch 聚类；没有把三个种子乘成三倍图片。

主结果是 Holm 校正后的近似 cluster-t p 值。原图片 bootstrap 区间与另算的 Bonferroni cluster-t 近似同时区间均保留在 JSON/CSV；它们不是 Holm/BH 区间。BH 仅作探索，其依赖条件未在本实验中验证。不拒绝零差异不等于证明等效或无差异。

| 目标 | 方法 A − B | ΔASR／百分点 | 原始 p | Holm p | BH p（探索） | Holm 拒绝零差异 | 状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20_fixed_step | -2.94 | 0.005 | 0.165 | 0.008077 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20 | -1.16 | 0.3107 | 1 | 0.3389 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20_fixed_step | -6.72 | 1.234e-06 | 6.539e-05 | 3.239e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20 | -4.94 | 0.0001407 | 0.005768 | 0.0002686 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − mi_g24_fixed_step | -1.33 | 0.1424 | 1 | 0.1685 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − mi_g24 | +0.98 | 0.3376 | 1 | 0.359 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g24 − mi_g24_fixed_step | -4.59 | 1.444e-05 | 0.0006643 | 3.11e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g24 − mi_g24 | -2.28 | 0.02802 | 0.7837 | 0.04057 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − mi_g28_fixed_step | +0.11 | 0.913 | 1 | 0.9223 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − mi_g28 | +1.68 | 0.08341 | 1 | 0.1046 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g28 − mi_g28_fixed_step | -3.26 | 0.001387 | 0.05132 | 0.002427 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g28 − mi_g28 | -1.68 | 0.1359 | 1 | 0.1631 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − mi_g32_fixed_step | +1.19 | 0.2393 | 1 | 0.268 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − mi_g32 | +2.66 | 0.01061 | 0.3289 | 0.0165 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g32 − mi_g32_fixed_step | -2.24 | 0.03316 | 0.8622 | 0.04721 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g32 − mi_g32 | -0.77 | 0.5235 | 1 | 0.5429 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − mi_g36_fixed_step | +1.93 | 0.07648 | 1 | 0.09733 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − mi_g36 | +5.29 | 2.521e-06 | 0.0001286 | 6.227e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g36 − mi_g36_fixed_step | -1.19 | 0.3271 | 1 | 0.3523 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g36 − mi_g36 | +2.17 | 0.07105 | 1 | 0.09181 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40_fixed_step | +2.17 | 0.04029 | 1 | 0.0564 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40 | +4.80 | 4.357e-06 | 0.0002179 | 1.046e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40_fixed_step | -0.11 | 0.9223 | 1 | 0.9223 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40 | +2.52 | 0.01302 | 0.3907 | 0.01989 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80_fixed_step | +6.55 | 5.721e-09 | 3.547e-07 | 2.089e-08 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80 | +9.49 | 4.991e-13 | 3.745e-11 | 3.953e-12 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80_fixed_step | +4.31 | 3.07e-05 | 0.00132 | 6.14e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80 | +7.25 | 3.584e-10 | 2.366e-08 | 1.585e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20_fixed_step | +4.24 | 2.431e-05 | 0.001094 | 5.105e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20 | +5.30 | 9.223e-06 | 0.0004427 | 2.094e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20_fixed_step | +3.60 | 0.0006959 | 0.02645 | 0.001244 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20 | +4.66 | 3.291e-05 | 0.001382 | 6.429e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − mi_g24_fixed_step | +7.24 | 3.856e-09 | 2.429e-07 | 1.472e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − mi_g24 | +7.13 | 2.348e-09 | 1.526e-07 | 9.861e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g24 − mi_g24_fixed_step | +6.21 | 1.545e-06 | 8.036e-05 | 3.933e-06 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g24 − mi_g24 | +6.11 | 5.371e-07 | 2.9e-05 | 1.455e-06 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − mi_g28_fixed_step | +9.11 | 3.318e-11 | 2.322e-09 | 1.858e-10 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − mi_g28 | +8.37 | 2.749e-10 | 1.842e-08 | 1.283e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g28 − mi_g28_fixed_step | +8.02 | 6.364e-09 | 3.882e-07 | 2.227e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g28 − mi_g28 | +7.27 | 4.594e-08 | 2.665e-06 | 1.429e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − mi_g32_fixed_step | +11.16 | 2.618e-14 | 2.042e-12 | 3.142e-13 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − mi_g32 | +9.57 | 2.92e-12 | 2.132e-10 | 2.044e-11 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g32 − mi_g32_fixed_step | +9.96 | 1.224e-11 | 8.691e-10 | 7.344e-11 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g32 − mi_g32 | +8.37 | 3.509e-09 | 2.246e-07 | 1.404e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − mi_g36_fixed_step | +12.61 | 4.418e-15 | 3.49e-13 | 6.185e-14 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − mi_g36 | +10.81 | 5.176e-13 | 3.831e-11 | 3.953e-12 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g36 − mi_g36_fixed_step | +11.02 | 3.417e-12 | 2.46e-10 | 2.208e-11 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g36 − mi_g36 | +9.22 | 2.02e-10 | 1.394e-08 | 1.061e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40_fixed_step | +13.42 | 1.017e-15 | 8.134e-14 | 1.708e-14 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40 | +11.62 | 5.762e-14 | 4.437e-12 | 6.05e-13 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40_fixed_step | +11.37 | 4.928e-13 | 3.745e-11 | 3.953e-12 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40 | +9.57 | 2.426e-10 | 1.65e-08 | 1.199e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80_fixed_step | +21.15 | 1.28e-22 | 1.075e-20 | 1.075e-20 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80 | +16.81 | 4.649e-19 | 3.813e-17 | 1.302e-17 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80_fixed_step | +19.53 | 1.107e-20 | 9.185e-19 | 4.648e-19 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80 | +15.18 | 8.514e-19 | 6.896e-17 | 1.788e-17 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − bsr_m4_g20 | +3.78 | 2.417e-07 | 1.329e-05 | 6.768e-07 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g20_fixed_step − mi_g20 | +1.79 | 0.09179 | 1 | 0.1134 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − bsr_m4_g24 | +3.26 | 1.24e-08 | 7.442e-07 | 4.167e-08 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g24_fixed_step − mi_g24 | +2.31 | 0.02799 | 0.7837 | 0.04057 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − bsr_m4_g28 | +3.36 | 1.672e-08 | 9.862e-07 | 5.4e-08 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g28_fixed_step − mi_g28 | +1.58 | 0.1675 | 1 | 0.1927 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − bsr_m4_g32 | +3.43 | 1.515e-07 | 8.636e-06 | 4.545e-07 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g32_fixed_step − mi_g32 | +1.47 | 0.2041 | 1 | 0.2317 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − bsr_m4_g36 | +3.12 | 1.993e-07 | 1.116e-05 | 5.774e-07 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g36_fixed_step − mi_g36 | +3.36 | 0.0034 | 0.1156 | 0.0056 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − bsr_m4_g40 | +2.28 | 7.979e-06 | 0.000391 | 1.862e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g40_fixed_step − mi_g40 | +2.63 | 0.01945 | 0.564 | 0.02917 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − bsr_m4_g80 | +2.24 | 1.054e-05 | 0.0004952 | 2.329e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g80_fixed_step − mi_g80 | +2.94 | 0.002257 | 0.07899 | 0.003792 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − bsr_m4_g20 | +0.64 | 0.1516 | 1 | 0.1769 | 否 | ok |
| cifar10_vgg11_bn | mi_g20_fixed_step − mi_g20 | +1.06 | 0.2677 | 1 | 0.2959 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − bsr_m4_g24 | +1.02 | 0.06317 | 1 | 0.08422 | 否 | ok |
| cifar10_vgg11_bn | mi_g24_fixed_step − mi_g24 | -0.11 | 0.9042 | 1 | 0.9223 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − bsr_m4_g28 | +1.09 | 0.05462 | 1 | 0.074 | 否 | ok |
| cifar10_vgg11_bn | mi_g28_fixed_step − mi_g28 | -0.74 | 0.3972 | 1 | 0.4171 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − bsr_m4_g32 | +1.20 | 0.008084 | 0.2587 | 0.01281 | 否 | ok |
| cifar10_vgg11_bn | mi_g32_fixed_step − mi_g32 | -1.59 | 0.1244 | 1 | 0.1514 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − bsr_m4_g36 | +1.59 | 0.001699 | 0.06118 | 0.002913 | 否 | ok |
| cifar10_vgg11_bn | mi_g36_fixed_step − mi_g36 | -1.80 | 0.07031 | 1 | 0.09181 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − bsr_m4_g40 | +2.05 | 2.682e-05 | 0.00118 | 5.495e-05 | 是 | ok |
| cifar10_vgg11_bn | mi_g40_fixed_step − mi_g40 | -1.80 | 0.05423 | 1 | 0.074 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − bsr_m4_g80 | +1.62 | 0.0002692 | 0.01077 | 0.0005026 | 是 | ok |
| cifar10_vgg11_bn | mi_g80_fixed_step − mi_g80 | -4.34 | 0.0002754 | 0.01077 | 0.0005029 | 是 | ok |

只有一个有效 cluster 或 cluster 方差为零时不报告确定的 p 值；相关行保留在家族大小中。正差值表示 A 的 ASR 更高，拒绝零差异本身不表示差异方向为正。

完整条件、输入 SHA256、各对照有效图片数与 batch 数见 [JSON](multiplicity.json)；便于查看的表格见 [CSV](multiplicity.csv)。

该目录为新建分析输出；未修改原始结果或重新运行模型、攻击。
