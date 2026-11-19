"""Postprocess saved predictions only. No torch, model, attack or API calls."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
run, output = args.run.resolve(), args.output.resolve()
project = run.parents[1]
sys.path.insert(0, str(project))
from course_tools.v1_metrics import paired_bootstrap
from course_tools import v1_multiplicity as multi

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')

def read_csv(name):
    with (run / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))

def write_csv(path, rows, columns=None):
    if columns is None:
        columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

completion = read_json(run / 'completion.json')
original_hashes = {name: sha(run / name) for name in completion['sha256']}
assert original_hashes == completion['sha256'], 'Original completion hashes differ'
config = read_json(run / 'config.frozen.json')
original = read_json(run / 'results.json')
selection = read_json(run / 'selection.json')
provenance = read_json(run / 'provenance.json')
for name, expected in provenance['source_sha256'].items():
    assert sha(run / 'source_snapshot' / name) == expected, name
assert original['api_calls'] == 0
assert original['images'] == 1000
assert len(original['jobs']) == 56

output.mkdir(parents=True, exist_ok=True)
data = output / 'data'
data.mkdir(exist_ok=True)
(output / 'statistics').mkdir(exist_ok=True)

target_names = {'cifar10_mobilenetv2_x1_0': 'MobileNetV2', 'cifar10_vgg11_bn': 'VGG11-BN'}
subset_names = {'full1000': '全部1000张', 'pilot200': '原预实验200张', 'new800': '排除原预实验的800张'}

def method_label(name):
    if name.startswith('bsr_m2_'):
        return 'BSR双视图'
    if name.startswith('bsr_m4_'):
        return 'BSR四视图'
    return 'MI固定步长' if name.endswith('_fixed_step') else 'MI按步数缩放'

context_base = multi.inspect_run(run, 'full1000', 'all')
predictions = multi.load_predictions(context_base)
all_rows, crossings, statistics = [], [], {}
for subset in ['full1000', 'new800', 'pilot200']:
    context = multi.inspect_run(run, subset, 'all')
    comparisons = [dict(row, comparison_origin='原运行记录') for row in context['comparisons']]
    positions = context['positions']
    labels = predictions['labels'][positions]
    for target in original['targets']:
        clean = predictions['clean'][target][positions]
        for budget in config['gradient_budgets']:
            for first, second in [(f'bsr_m2_g{budget}', f'bsr_m4_g{budget}'),
                                  (f'mi_g{budget}_fixed_step', f'mi_g{budget}')]:
                arrays = []
                for name in [first, second]:
                    arrays.append(np.stack([predictions['adversarial'][(target, name, seed)][positions]
                                            for seed in original['methods'][name]['seeds']]))
                result = paired_bootstrap(labels, clean, arrays[0], arrays[1],
                                          seed=config['bootstrap_seed'], n_bootstrap=config['bootstrap_replicates'])
                comparisons.append({'target': target, 'subset': subset, 'method_a': first, 'method_b': second,
                                    'gradient_budget': budget, 'comparison_origin': '由保存预测补算', **result})
    assert len(comparisons) == 84
    context['comparisons'] = comparisons
    context['family'] = 'all_six_pairwise_contrasts'
    result = multi.analyse(context)
    result['preprocessor_sha256'] = sha(Path(__file__))
    result['original_comparisons'] = 56
    result['additional_comparisons'] = 28
    result['joint_control_across_subsets_claimed'] = False
    result['notes'].append('Family expanded post hoc to all six method pairs per target/budget: 84 comparisons per subset. Original BSR-vs-MI family had 56. No independent confirmation or threshold-confidence claim.')
    multi.write_report(output / 'statistics' / subset, result)
    statistics[subset] = result
    by_key = {(r['target'], r['method_a'], r['method_b']): r for r in result['comparisons']}
    for row in comparisons:
        stats = by_key[(row['target'], row['method_a'], row['method_b'])]
        ci = row['ci95']
        simultaneous = stats['bonferroni_cluster_t_simultaneous_ci']
        flat = {key: value for key, value in row.items() if key != 'ci95'}
        flat.update(target_cn=target_names[row['target']], subset_cn=subset_names[subset],
                    method_a_cn=method_label(row['method_a']), method_b_cn=method_label(row['method_b']),
                    comparison_cn=method_label(row['method_a']) + ' − ' + method_label(row['method_b']),
                    ci95_lower=ci[0], ci95_upper=ci[1],
                    p_raw_cluster_t=stats['p_raw_cluster_t'], p_holm=stats['p_holm'],
                    p_bh_exploratory=stats['p_bh_exploratory'], reject_holm=stats['reject_holm'],
                    cluster_count=stats['cluster_count'], cluster_standard_error=stats['cluster_standard_error'],
                    degrees_of_freedom=stats['degrees_of_freedom'],
                    bonferroni_ci_lower=simultaneous[0] if simultaneous else None,
                    bonferroni_ci_upper=simultaneous[1] if simultaneous else None,
                    multiplicity_family_size=84,
                    image_interval_interpretation=('A较高，逐点区间高于零' if ci[0] > 1e-12 else
                                                   'A较低，逐点区间低于零' if ci[1] < -1e-12 else '区间含零，差异证据不足'),
                    holm_interpretation=('正向差异在本次校正中保留' if stats['reject_holm'] and row['difference_a_minus_b'] > 0 else
                                         '负向差异在本次校正中保留' if stats['reject_holm'] else '本方法下未拒绝零差异'))
        all_rows.append(flat)
    for target in original['targets']:
        groups = {}
        for row in (r for r in comparisons if r['target'] == target):
            family = (method_label(row['method_a']), method_label(row['method_b']))
            groups.setdefault(family, []).append(row)
        for (first, second), rows in groups.items():
            rows.sort(key=lambda r: r['gradient_budget'])
            flips = []
            for left, right in zip(rows, rows[1:]):
                dl, dr = left['difference_a_minus_b'], right['difference_a_minus_b']
                if dl * dr < 0 and abs(dl) > 1e-12 and abs(dr) > 1e-12:
                    endpoint_support = ((left['ci95'][1] < -1e-12 and right['ci95'][0] > 1e-12) or
                                        (left['ci95'][0] > 1e-12 and right['ci95'][1] < -1e-12))
                    flips.append({'lower_budget': left['gradient_budget'], 'upper_budget': right['gradient_budget'],
                                  'direction': '负转正' if dl < 0 else '正转负',
                                  'both_endpoint_image_intervals_exclude_zero': endpoint_support,
                                  'interpretation': '两端逐点区间均排除零；仍非交叉点置信区间' if endpoint_support else '仅采样均值变号；端点区间不足以确定稳定换优'})
            crossings.append({'target': target, 'target_cn': target_names[target], 'subset': subset,
                              'subset_cn': subset_names[subset], 'method_a_cn': first, 'method_b_cn': second,
                              'flips': flips, 'all_sampled_means_positive': all(r['difference_a_minus_b'] > 1e-12 for r in rows),
                              'all_sampled_means_negative': all(r['difference_a_minus_b'] < -1e-12 for r in rows)})

all_rows.sort(key=lambda r: (['full1000','new800','pilot200'].index(r['subset']), list(original['targets']).index(r['target']), r['gradient_budget'], r['comparison_cn']))
write_csv(data / 'all_comparisons.csv', all_rows)

header_map = {
    'target':'目标模型', 'subset':'图片集合', 'method':'方法编号', 'steps':'更新步数T', 'views':'每步视图数M',
    'gradient_budget':'每图梯度预算G', 'alpha':'单步像素步长', 'alpha_kind':'步长规则', 'sample_count':'集合图片数',
    'attack_seed_count':'攻击种子数', 'clean_accuracy':'原图准确率', 'robust_accuracy':'攻击后准确率',
    'asr_numerator':'攻击成功图片数_种子均值', 'asr_denominator':'目标原图认对数量', 'asr':'条件攻击成功率',
    'asr_seed_min':'种子成功率最低值', 'asr_seed_max':'种子成功率最高值', 'asr_seed_std':'种子成功率样本标准差',
    'source_asr':'代理白盒攻击成功率', 'mean_attack_seconds':'完整1000张每种子平均生成秒数', 'timing_scope':'计时口径',
    'seed_index':'种子序号', 'seed':'攻击基础种子', 'attack_seconds':'该种子完整1000张生成秒数',
    'method_a':'方法A编号', 'method_b':'方法B编号', 'attack_seed_count_a':'方法A种子数', 'attack_seed_count_b':'方法B种子数',
    'asr_a':'方法A成功率', 'asr_b':'方法B成功率', 'difference_a_minus_b':'成功率差_A减B_比例',
    'bootstrap_seed':'统计重采样种子', 'bootstrap_requested':'计划统计重采样次数', 'bootstrap_valid':'有效统计重采样次数',
    'bootstrap_skipped_zero_denominator':'分母为零而跳过的次数', 'resampling_unit':'统计抽样单位',
    'ci95_lower':'图片配对95%区间下限_比例', 'ci95_upper':'图片配对95%区间上限_比例',
    'test_id':'原测试集图片编号', 'label':'真实类别编号', 'clean_prediction':'目标原图预测类别',
    'adversarial_prediction':'目标攻击后预测类别', 'source_clean_prediction':'代理原图预测类别',
    'source_adversarial_prediction':'代理攻击后预测类别', 'linf':'最大绝对像素扰动', 'in_pilot200':'属于原200张预实验'
}
translated_files = {'summary.csv':'方法汇总_中文.csv','per_seed.csv':'种子明细_中文.csv',
                    'comparisons.csv':'原配对比较_中文.csv','predictions.csv':'完整逐图预测_中文.csv'}
row_counts = {}
for name, destination in translated_files.items():
    rows = read_csv(name)
    row_counts[name] = len(rows)
    translated = []
    for row in rows:
        converted = {}
        for key, value in row.items():
            if key == 'target': value = target_names[value]
            elif key == 'subset': value = subset_names[value]
            elif key == 'alpha_kind': value = {'fixed_epsilon_over_denominator':'固定步长ε/10','epsilon_over_steps':'按更新步数ε/T'}[value]
            elif key == 'timing_scope': value = '完整1000张每种子生成；跨目标与集合复用；不含预热和评价'
            elif key == 'resampling_unit': value = '按图片配对抽样，保留全部方法与攻击种子'
            elif key == 'in_pilot200': value = '是' if value == 'True' else '否'
            column = header_map[key]
            if name == 'per_seed.csv' and key == 'asr_numerator': column = '该种子攻击成功图片数'
            converted[column] = value
        translated.append(converted)
    write_csv(data / destination, translated)

seed_rows = read_csv('per_seed.csv')
unique_generation = [r for r in seed_rows if r['target'] == config['target_models'][0] and r['subset'] == 'full1000']
assert len(unique_generation) == 56
assert 'torch' not in sys.modules, 'Postprocessing unexpectedly imported torch'
manifest = {
    'run': str(run), 'completed_at': original['completed_at'], 'source': original['source'],
    'targets': config['target_models'], 'target_names': target_names, 'subset_names': subset_names,
    'gradient_budgets': config['gradient_budgets'], 'views': config['views'], 'mi_step_rules': config['mi_step_rules'],
    'bsr_seeds': config['bsr_seeds'], 'sample_count': 1000, 'epsilon': config['epsilon'], 'batch_size': config['batch_size'],
    'method_count': len(original['methods']), 'job_count': len(original['jobs']),
    'sample_view_gradients': original['total_sample_view_gradient_evaluations'],
    'row_counts': row_counts, 'all_pair_comparison_rows': len(all_rows), 'family_size_per_subset':84,
    'total_generation_seconds': sum(float(r['attack_seconds']) for r in unique_generation),
    'original_completion_sha256': original_hashes,
    'additional_image_bootstrap_pairs': 84, 'bootstrap_replicates': config['bootstrap_replicates'],
    'postprocessing_model_calls':0, 'postprocessing_attack_runs':0, 'postprocessing_api_calls':0,
    'headers_cn':header_map, 'crossovers':crossings,
    'method_labels': {name:method_label(name) for name in original['methods']},
    'statistics': {subset:{'family_size':r['family_size'],'holm_reject_count':sum(x['reject_holm'] is True for x in r['comparisons']),
                           'joint_across_subsets':False,'numpy':r['numpy_version'],'scipy':r['scipy_version']}
                   for subset,r in statistics.items()},
    'limitations': [
        '全部1000张已参与探索；新增800张与全1000张重叠，不是独立确认。',
        '图片配对区间条件于当前模型和三个已实现攻击种子；共享batch几何和训练不确定性不在该区间内。',
        'Holm采用按原batch聚类的t近似，并在每个集合全部84个方法对上事后统一校正；不是精确有限样本或独立确认。',
        'BH仅作探索，其依赖条件未在本实验中验证；Bonferroni聚类t近似同时区间另列，不称Holm区间。',
        '采样均值翻转区间不是交叉点的置信区间，不保证连续性、单调性或唯一阈值。',
        'MI固定步长与按步数缩放均保留；BSR使用ε/T，预算改变同时影响其步长日程。',
        '耗时为完整1000张每种子的单次观察，跨目标和子集复用；不同模型结果行不可重复加总。',
        '当前共同M2/M4预算需为4的倍数，原notes中最细间隔2不会自动执行，单独M2才可细化到2。'
    ]
}
write_json(output / 'analysis.json', manifest)
for name, expected in original_hashes.items():
    assert sha(run / name) == expected, 'Original run was modified: ' + name
print(json.dumps({'output':str(output),'comparison_rows':len(all_rows),'row_counts':row_counts,
                  'job_count':56,'gradients':manifest['sample_view_gradients'],'source_hashes_unchanged':True,
                  'postprocessing_attack_runs':0},ensure_ascii=False))
