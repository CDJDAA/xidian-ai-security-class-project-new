# V1 多重比较敏感性检查

集合：`pilot200`；家族：`all_six_pairwise_contrasts`；共 84 个记录中的对照；α=0.05。

这是对已观察数据的事后敏感性检查，条件于当前模型和已有攻击种子，不是新实验或独立确认。每张图先平均种子，再按原生成 batch 聚类；没有把三个种子乘成三倍图片。

主结果是 Holm 校正后的近似 cluster-t p 值。原图片 bootstrap 区间与另算的 Bonferroni cluster-t 近似同时区间均保留在 JSON/CSV；它们不是 Holm/BH 区间。BH 仅作探索，其依赖条件未在本实验中验证。不拒绝零差异不等于证明等效或无差异。

| 目标 | 方法 A − B | ΔASR／百分点 | 原始 p | Holm p | BH p（探索） | Holm 拒绝零差异 | 状态 |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20_fixed_step | -2.60 | 0.2322 | 1 | 0.39 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − mi_g20 | -2.08 | 0.3114 | 1 | 0.4844 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20_fixed_step | -5.21 | 0.06143 | 1 | 0.1259 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g20 − mi_g20 | -4.69 | 0.06553 | 1 | 0.128 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − mi_g24_fixed_step | +0.69 | 0.7892 | 1 | 0.843 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − mi_g24 | +1.74 | 0.4479 | 1 | 0.596 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g24 − mi_g24_fixed_step | -2.95 | 0.2806 | 1 | 0.4533 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g24 − mi_g24 | -1.91 | 0.3521 | 1 | 0.5188 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − mi_g28_fixed_step | -0.00 | 1 | 1 | 1 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − mi_g28 | +2.08 | 0.4146 | 1 | 0.5738 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g28 − mi_g28_fixed_step | -1.91 | 0.4705 | 1 | 0.5988 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g28 − mi_g28 | +0.17 | 0.9426 | 1 | 0.954 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − mi_g32_fixed_step | -0.17 | 0.9322 | 1 | 0.954 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − mi_g32 | +1.91 | 0.451 | 1 | 0.596 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g32 − mi_g32_fixed_step | -1.74 | 0.4612 | 1 | 0.596 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g32 − mi_g32 | +0.35 | 0.8953 | 1 | 0.9284 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − mi_g36_fixed_step | +2.08 | 0.3325 | 1 | 0.5078 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − mi_g36 | +4.69 | 0.01789 | 0.9303 | 0.04554 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g36 − mi_g36_fixed_step | -0.87 | 0.7174 | 1 | 0.8038 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g36 − mi_g36 | +1.74 | 0.3656 | 1 | 0.5295 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40_fixed_step | +1.22 | 0.5505 | 1 | 0.6758 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − mi_g40 | +4.86 | 0.02547 | 1 | 0.06292 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40_fixed_step | -0.87 | 0.6762 | 1 | 0.7781 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g40 − mi_g40 | +2.78 | 0.1999 | 1 | 0.3427 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80_fixed_step | +7.99 | 0.006781 | 0.3662 | 0.01808 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − mi_g80 | +9.55 | 0.001005 | 0.06329 | 0.003836 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80_fixed_step | +5.56 | 0.02841 | 1 | 0.0663 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m4_g80 − mi_g80 | +7.12 | 0.00579 | 0.3301 | 0.01668 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20_fixed_step | +4.91 | 0.03401 | 1 | 0.07722 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − mi_g20 | +8.60 | 0.001502 | 0.0916 | 0.005256 | 否 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20_fixed_step | +4.21 | 0.02754 | 1 | 0.06609 | 否 | ok |
| cifar10_vgg11_bn | bsr_m4_g20 − mi_g20 | +7.89 | 0.0002853 | 0.01997 | 0.001598 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − mi_g24_fixed_step | +6.67 | 0.005958 | 0.3335 | 0.01668 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − mi_g24 | +8.77 | 0.0003992 | 0.02715 | 0.001932 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g24 − mi_g24_fixed_step | +6.49 | 0.005955 | 0.3335 | 0.01668 | 否 | ok |
| cifar10_vgg11_bn | bsr_m4_g24 − mi_g24 | +8.60 | 0.0008047 | 0.05231 | 0.00338 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − mi_g28_fixed_step | +9.12 | 0.0009478 | 0.06066 | 0.003791 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − mi_g28 | +11.23 | 2.632e-05 | 0.002027 | 0.0002764 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g28 − mi_g28_fixed_step | +8.77 | 0.006888 | 0.3662 | 0.01808 | 否 | ok |
| cifar10_vgg11_bn | bsr_m4_g28 − mi_g28 | +10.88 | 0.0001053 | 0.007901 | 0.0008849 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − mi_g32_fixed_step | +10.70 | 0.0001311 | 0.009571 | 0.0009178 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − mi_g32 | +12.28 | 2.838e-06 | 0.0002299 | 5.96e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g32 − mi_g32_fixed_step | +10.35 | 0.001256 | 0.07788 | 0.004588 | 否 | ok |
| cifar10_vgg11_bn | bsr_m4_g32 − mi_g32 | +11.93 | 0.0001685 | 0.01213 | 0.001089 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − mi_g36_fixed_step | +12.46 | 0.0001196 | 0.008847 | 0.0009129 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − mi_g36 | +12.98 | 4.118e-05 | 0.00313 | 0.0003843 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g36 − mi_g36_fixed_step | +11.75 | 0.000447 | 0.0295 | 0.001976 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g36 − mi_g36 | +12.28 | 0.0004141 | 0.02775 | 0.001932 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40_fixed_step | +14.21 | 0.0002505 | 0.01779 | 0.001503 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − mi_g40 | +14.74 | 7.694e-07 | 6.386e-05 | 2.781e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40_fixed_step | +11.93 | 0.0003648 | 0.02517 | 0.001915 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g40 − mi_g40 | +12.46 | 8.699e-06 | 0.0006959 | 0.0001461 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80_fixed_step | +19.12 | 1.379e-05 | 0.00109 | 0.0001931 | 是 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − mi_g80 | +18.07 | 7.266e-07 | 6.104e-05 | 2.781e-05 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80_fixed_step | +17.37 | 2.147e-05 | 0.001675 | 0.0002576 | 是 | ok |
| cifar10_vgg11_bn | bsr_m4_g80 − mi_g80 | +16.32 | 9.931e-07 | 8.144e-05 | 2.781e-05 | 是 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g20 − bsr_m4_g20 | +2.60 | 0.002019 | 0.1211 | 0.006783 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g20_fixed_step − mi_g20 | +0.52 | 0.6625 | 1 | 0.7729 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g24 − bsr_m4_g24 | +3.65 | 0.003026 | 0.1785 | 0.009776 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g24_fixed_step − mi_g24 | +1.04 | 0.6465 | 1 | 0.7729 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g28 − bsr_m4_g28 | +1.91 | 0.1597 | 1 | 0.2795 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g28_fixed_step − mi_g28 | +2.08 | 0.2952 | 1 | 0.4678 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g32 − bsr_m4_g32 | +1.56 | 0.09414 | 1 | 0.1775 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g32_fixed_step − mi_g32 | +2.08 | 0.2585 | 1 | 0.4258 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g36 − bsr_m4_g36 | +2.95 | 0.003779 | 0.2192 | 0.01176 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g36_fixed_step − mi_g36 | +2.60 | 0.09507 | 1 | 0.1775 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g40 − bsr_m4_g40 | +2.08 | 0.05393 | 1 | 0.1133 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g40_fixed_step − mi_g40 | +3.65 | 0.03837 | 1 | 0.08265 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | bsr_m2_g80 − bsr_m4_g80 | +2.43 | 0.1356 | 1 | 0.2476 | 否 | ok |
| cifar10_mobilenetv2_x1_0 | mi_g80_fixed_step − mi_g80 | +1.56 | 0.4167 | 1 | 0.5738 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g20 − bsr_m4_g20 | +0.70 | 0.4581 | 1 | 0.596 | 否 | ok |
| cifar10_vgg11_bn | mi_g20_fixed_step − mi_g20 | +3.68 | 0.1397 | 1 | 0.2497 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g24 − bsr_m4_g24 | +0.18 | 0.8261 | 1 | 0.8674 | 否 | ok |
| cifar10_vgg11_bn | mi_g24_fixed_step − mi_g24 | +2.11 | 0.3399 | 1 | 0.5098 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g28 − bsr_m4_g28 | +0.35 | 0.7273 | 1 | 0.8038 | 否 | ok |
| cifar10_vgg11_bn | mi_g28_fixed_step − mi_g28 | +2.11 | 0.3739 | 1 | 0.5323 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g32 − bsr_m4_g32 | +0.35 | 0.7266 | 1 | 0.8038 | 否 | ok |
| cifar10_vgg11_bn | mi_g32_fixed_step − mi_g32 | +1.58 | 0.4894 | 1 | 0.6136 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g36 − bsr_m4_g36 | +0.70 | 0.5551 | 1 | 0.6758 | 否 | ok |
| cifar10_vgg11_bn | mi_g36_fixed_step − mi_g36 | +0.53 | 0.7531 | 1 | 0.8216 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g40 − bsr_m4_g40 | +2.28 | 0.03747 | 1 | 0.08265 | 否 | ok |
| cifar10_vgg11_bn | mi_g40_fixed_step − mi_g40 | +0.53 | 0.7928 | 1 | 0.843 | 否 | ok |
| cifar10_vgg11_bn | bsr_m2_g80 − bsr_m4_g80 | +1.75 | 0.06469 | 1 | 0.128 | 否 | ok |
| cifar10_vgg11_bn | mi_g80_fixed_step − mi_g80 | -1.05 | 0.6615 | 1 | 0.7729 | 否 | ok |

只有一个有效 cluster 或 cluster 方差为零时不报告确定的 p 值；相关行保留在家族大小中。正差值表示 A 的 ASR 更高，拒绝零差异本身不表示差异方向为正。

完整条件、输入 SHA256、各对照有效图片数与 batch 数见 [JSON](multiplicity.json)；便于查看的表格见 [CSV](multiplicity.csv)。

该目录为新建分析输出；未修改原始结果或重新运行模型、攻击。
