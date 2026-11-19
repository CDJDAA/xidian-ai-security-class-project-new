# V1 多重比较敏感性检查

集合：`new800`；家族：`all_six_pairwise_contrasts`；共 84 个记录中的对照；α=0.05。

这是对已观察数据的事后敏感性检查，条件于当前模型和已有攻击种子，不是新实验或独立确认。每张图先平均种子，再按原生成 batch 聚类；没有把三个种子乘成三倍图片。

主结果是 Holm 校正后的近似 cluster-t p 值。原图片 bootstrap 区间与另算的 Bonferroni cluster-t 近似同时区间均保留在 JSON/CSV；它们不是 Holm/BH 区间。BH 仅作探索，其依赖条件未在本实验中验证。不拒绝零差异不等于证明等效或无差异。

| 目标 | 方法 A − B | ΔASR／百分点 | 原始 p | Holm p | BH p（探索） | Holm 拒绝零差异 | 状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20_fixed_step | -3.03 | 0.01212 | 0.3877 | 0.0192 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20 | -0.92 | 0.4892 | 1 | 0.5147 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20_fixed_step | -7.11 | 1.107e-05 | 0.000609 | 3.1e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20 | -5.00 | 0.000869 | 0.03618 | 0.001659 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − mi_g24_fixed_step | -1.84 | 0.09449 | 1 | 0.1193 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − mi_g24 | +0.79 | 0.5135 | 1 | 0.5325 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g24 − mi_g24_fixed_step | -5.00 | 7.443e-05 | 0.003498 | 0.0001645 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g24 − mi_g24 | -2.37 | 0.05011 | 1 | 0.07016 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − mi_g28_fixed_step | +0.13 | 0.9076 | 1 | 0.9185 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − mi_g28 | +1.58 | 0.1357 | 1 | 0.1605 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g28 − mi_g28_fixed_step | -3.60 | 0.002326 | 0.08838 | 0.004157 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g28 − mi_g28 | -2.15 | 0.09512 | 1 | 0.1193 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − mi_g32_fixed_step | +1.54 | 0.2011 | 1 | 0.2315 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − mi_g32 | +2.85 | 0.01784 | 0.553 | 0.02775 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g32 − mi_g32_fixed_step | -2.37 | 0.05605 | 1 | 0.07594 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g32 − mi_g32 | -1.05 | 0.4451 | 1 | 0.4793 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − mi_g36_fixed_step | +1.89 | 0.1425 | 1 | 0.1663 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − mi_g36 | +5.44 | 4.18e-05 | 0.002174 | 0.0001064 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g36 − mi_g36_fixed_step | -1.27 | 0.3735 | 1 | 0.4074 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g36 − mi_g36 | +2.28 | 0.1109 | 1 | 0.135 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40_fixed_step | +2.41 | 0.05868 | 1 | 0.07824 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40 | +4.78 | 5.798e-05 | 0.002899 | 0.0001392 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40_fixed_step | +0.09 | 0.9452 | 1 | 0.9452 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40 | +2.46 | 0.02906 | 0.8427 | 0.04359 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80_fixed_step | +6.18 | 3.688e-07 | 2.286e-05 | 1.347e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80 | +9.47 | 1.229e-10 | 9.467e-09 | 1.291e-09 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80_fixed_step | +3.99 | 0.0005204 | 0.02238 | 0.001041 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80 | +7.28 | 1.93e-08 | 1.332e-06 | 1.013e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20_fixed_step | +4.07 | 0.0004639 | 0.02041 | 0.0009505 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20 | +4.47 | 0.0008614 | 0.03618 | 0.001659 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20_fixed_step | +3.45 | 0.00558 | 0.1953 | 0.009373 | 否 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20 | +3.85 | 0.002734 | 0.1011 | 0.004784 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − mi_g24_fixed_step | +7.38 | 2.339e-07 | 1.497e-05 | 9.356e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − mi_g24 | +6.72 | 5.612e-07 | 3.423e-05 | 1.964e-06 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g24 − mi_g24_fixed_step | +6.15 | 4.583e-05 | 0.002337 | 0.0001132 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g24 − mi_g24 | +5.48 | 6.202e-05 | 0.003039 | 0.0001447 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − mi_g28_fixed_step | +9.11 | 6.531e-09 | 4.572e-07 | 3.657e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − mi_g28 | +7.65 | 2.675e-07 | 1.685e-05 | 1.021e-06 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g28 − mi_g28_fixed_step | +7.82 | 2.233e-07 | 1.452e-05 | 9.356e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g28 − mi_g28 | +6.37 | 1.263e-05 | 0.0006694 | 3.315e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − mi_g32_fixed_step | +11.27 | 7.1e-12 | 5.538e-10 | 8.519e-11 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − mi_g32 | +8.89 | 5.209e-09 | 3.698e-07 | 3.125e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g32 − mi_g32_fixed_step | +9.86 | 1.546e-09 | 1.129e-07 | 1.082e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g32 − mi_g32 | +7.47 | 1.205e-06 | 7.23e-05 | 4.049e-06 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − mi_g36_fixed_step | +12.64 | 3.258e-12 | 2.574e-10 | 4.561e-11 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − mi_g36 | +10.26 | 6.365e-10 | 4.71e-08 | 4.861e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g36 − mi_g36_fixed_step | +10.83 | 1.797e-09 | 1.294e-07 | 1.161e-08 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g36 − mi_g36 | +8.44 | 6.661e-08 | 4.529e-06 | 3.291e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40_fixed_step | +13.22 | 5.944e-13 | 4.755e-11 | 9.986e-12 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40 | +10.83 | 3.051e-10 | 2.288e-08 | 2.563e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40_fixed_step | +11.23 | 2.665e-10 | 2.025e-08 | 2.487e-09 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40 | +8.84 | 2.154e-07 | 1.421e-05 | 9.356e-07 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80_fixed_step | +21.66 | 4.112e-20 | 3.454e-18 | 3.454e-18 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80 | +16.49 | 4.42e-15 | 3.624e-13 | 1.237e-13 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80_fixed_step | +20.07 | 3.7e-18 | 3.071e-16 | 1.554e-16 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80 | +14.90 | 5.932e-15 | 4.805e-13 | 1.246e-13 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − bsr_m4_g20 | +4.08 | 4.563e-06 | 0.0002601 | 1.369e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g20_fixed_step − mi_g20 | +2.11 | 0.1004 | 1 | 0.1241 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − bsr_m4_g24 | +3.16 | 2.286e-06 | 0.0001326 | 7.111e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g24_fixed_step − mi_g24 | +2.63 | 0.03283 | 0.9192 | 0.04838 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − bsr_m4_g28 | +3.73 | 8.612e-08 | 5.77e-06 | 4.019e-07 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g28_fixed_step − mi_g28 | +1.45 | 0.2722 | 1 | 0.3048 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − bsr_m4_g32 | +3.90 | 1.523e-06 | 8.983e-05 | 4.919e-06 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g32_fixed_step − mi_g32 | +1.32 | 0.3324 | 1 | 0.3674 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − bsr_m4_g36 | +3.16 | 8.2e-06 | 0.0004592 | 2.375e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g36_fixed_step − mi_g36 | +3.55 | 0.008909 | 0.294 | 0.01439 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − bsr_m4_g40 | +2.32 | 7.05e-05 | 0.003384 | 0.0001601 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g40_fixed_step − mi_g40 | +2.37 | 0.07364 | 1 | 0.09517 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − bsr_m4_g80 | +2.19 | 1.212e-05 | 0.0006545 | 3.284e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g80_fixed_step − mi_g80 | +3.29 | 0.003681 | 0.1325 | 0.00631 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − bsr_m4_g20 | +0.62 | 0.2248 | 1 | 0.2551 | 否 | ok |
| cifar10_vgg11_bn | mi_g20_fixed_step − mi_g20 | +0.40 | 0.7009 | 1 | 0.7179 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − bsr_m4_g24 | +1.24 | 0.06365 | 1 | 0.08354 | 否 | ok |
| cifar10_vgg11_bn | mi_g24_fixed_step − mi_g24 | -0.66 | 0.4902 | 1 | 0.5147 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − bsr_m4_g28 | +1.28 | 0.05525 | 1 | 0.07594 | 否 | ok |
| cifar10_vgg11_bn | mi_g28_fixed_step − mi_g28 | -1.46 | 0.1141 | 1 | 0.137 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − bsr_m4_g32 | +1.41 | 0.005691 | 0.1953 | 0.009373 | 否 | ok |
| cifar10_vgg11_bn | mi_g32_fixed_step − mi_g32 | -2.39 | 0.03796 | 1 | 0.05498 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − bsr_m4_g36 | +1.81 | 0.001173 | 0.04691 | 0.002189 | 是 | ok |
| cifar10_vgg11_bn | mi_g36_fixed_step − mi_g36 | -2.39 | 0.04263 | 1 | 0.06069 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − bsr_m4_g40 | +1.99 | 0.0001113 | 0.005121 | 0.0002398 | 是 | ok |
| cifar10_vgg11_bn | mi_g40_fixed_step − mi_g40 | -2.39 | 0.02735 | 0.8204 | 0.04177 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − bsr_m4_g80 | +1.59 | 0.00225 | 0.08774 | 0.004108 | 否 | ok |
| cifar10_vgg11_bn | mi_g80_fixed_step − mi_g80 | -5.17 | 0.0001204 | 0.005418 | 0.0002528 | 是 | ok |

只有一个有效 cluster 或 cluster 方差为零时不报告确定的 p 值；相关行保留在家族大小中。正差值表示 A 的 ASR 更高，拒绝零差异本身不表示差异方向为正。

完整条件、输入 SHA256、各对照有效图片数与 batch 数见 [JSON](multiplicity.json)；便于查看的表格见 [CSV](multiplicity.csv)。

该目录为新建分析输出；未修改原始结果或重新运行模型、攻击。
