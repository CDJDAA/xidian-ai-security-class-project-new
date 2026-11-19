"""Independent audit of saved artifacts, without model queries or attack runs."""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from torchvision.datasets import CIFAR10
from torchvision.transforms import ToTensor

torch.set_num_threads(4)


parser = argparse.ArgumentParser()
parser.add_argument('--run', type=Path, required=True)
parser.add_argument('--data-root', type=Path, required=True)
parser.add_argument('--original-selection', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
run = args.run
results = json.loads((run / 'results.json').read_text())
config = json.loads((run / 'config.frozen.json').read_text())
selection = json.loads((run / 'selection.json').read_text())
original = json.loads(args.original_selection.read_text())
provenance = json.loads((run / 'provenance.json').read_text())
completion = json.loads((run / 'completion.json').read_text())
for relative, digest in completion['sha256'].items():
    assert hashlib.sha256((run/relative).read_bytes()).hexdigest() == digest, relative
for relative, digest in provenance['source_sha256'].items():
    assert hashlib.sha256((run/'source_snapshot'/relative).read_bytes()).hexdigest() == digest, relative
for relative, key in (('config.frozen.json','config_sha256'),('selection.json','selection_sha256')):
    assert hashlib.sha256((run/relative).read_bytes()).hexdigest() == provenance[key], relative

def extract_ids(mapping):
    for name in ('final_ids', 'ids', 'evaluation_ids', 'test_ids'):
        if name in mapping:
            return list(mapping[name])
    raise AssertionError('No evaluation IDs in selection')

ids = extract_ids(selection)
assert ids == original['final_ids'], 'Evaluation IDs differ from original frozen 1000'
assert len(ids) == len(set(ids)) == 1000
pilot = set(original['pilot_ids'])
assert len(pilot) == 200 and pilot <= set(ids)
subsets = {'full1000': set(ids), 'pilot200': pilot, 'new800': set(ids) - pilot}
assert len(subsets['new800']) == 800

with (run/'predictions.csv').open(newline='') as handle:
    rows = list(csv.DictReader(handle))
assert len(rows) == 50_000, len(rows)
groups = defaultdict(dict)
clean_by_target = defaultdict(dict)
source_clean = {}
labels = {}
for row in rows:
    target, method, seed = row['target'], row['method'], row['seed']
    image_id = int(row['test_id'])
    assert image_id in set(ids)
    key = target, method, seed
    assert image_id not in groups[key]
    groups[key][image_id] = row
    label, clean = int(row['label']), int(row['clean_prediction'])
    assert labels.setdefault(image_id, label) == label
    assert clean_by_target[target].setdefault(image_id, clean) == clean
    assert source_clean.setdefault(image_id, int(row['source_clean_prediction'])) == int(row['source_clean_prediction'])
    assert 0 <= float(row['linf']) <= 8/255 + 1e-6
assert len(groups) == 50, len(groups)
for group in groups.values():
    assert set(group) == set(ids)

methods = defaultdict(list)
for (target, method, seed), values in groups.items():
    methods[(target, method)].append((seed, values))
assert len(methods) == 26
independent = {}
for (target, method), seeded in methods.items():
    count = 3 if method.startswith('bsr_') else 1
    assert len(seeded) == count
    for subset_name, subset_ids in subsets.items():
        clean_count = sum(clean_by_target[target][i] == labels[i] for i in subset_ids)
        source_count = sum(source_clean[i] == labels[i] for i in subset_ids)
        successes, corrects, source_successes = [], [], []
        for seed, values in seeded:
            successes.append(sum(clean_by_target[target][i] == labels[i] and int(values[i]['adversarial_prediction']) != labels[i] for i in subset_ids))
            corrects.append(sum(int(values[i]['adversarial_prediction']) == labels[i] for i in subset_ids))
            source_successes.append(sum(source_clean[i] == labels[i] and int(values[i]['source_adversarial_prediction']) != labels[i] for i in subset_ids))
        independent[(target, method, subset_name)] = {
            'asr_numerator': sum(successes)/count,
            'asr_denominator': clean_count,
            'asr': sum(successes)/count/clean_count,
            'clean_accuracy': clean_count/len(subset_ids),
            'robust_accuracy': sum(corrects)/count/len(subset_ids),
            'source_asr': sum(source_successes)/count/source_count,
            'seed_success_counts': successes,
        }
assert len(results['summary']) == 78
for row in results['summary']:
    actual = independent[(row['target'], row['method'], row['subset'])]
    for key in ('asr_numerator', 'asr_denominator', 'asr', 'clean_accuracy', 'robust_accuracy', 'source_asr'):
        assert abs(float(row[key]) - actual[key]) < 1e-10, (row['target'],row['method'],row['subset'],key)

comparison_checks = []
independent_ci_checks = []
for comparison in results['comparisons']:
    a = independent[(comparison['target'], comparison['method_a'], comparison['subset'])]['asr']
    b = independent[(comparison['target'], comparison['method_b'], comparison['subset'])]['asr']
    assert abs(a-b-comparison['difference_a_minus_b']) < 1e-10
    comparison_checks.append({'target': comparison['target'], 'subset': comparison['subset'],
                              'method_a': comparison['method_a'], 'method_b': comparison['method_b'],
                              'difference_percentage_points': 100*(a-b), 'stored_ci95': comparison['ci95']})
    if comparison['gradient_budget'] == 40 and comparison['subset'] in ('full1000','new800') and comparison['method_b'] == 'mi_g40_fixed_step':
        target = comparison['target']
        ordered_ids = [i for i in ids if i in subsets[comparison['subset']]]
        correct = np.array([clean_by_target[target][i] == labels[i] for i in ordered_ids])
        def per_image_success(method_name):
            values = []
            for seed, predictions in methods[(target, method_name)]:
                values.append([int(predictions[i]['adversarial_prediction']) != labels[i] for i in ordered_ids])
            return correct * np.array(values).mean(axis=0)
        delta = per_image_success(comparison['method_a']) - per_image_success(comparison['method_b'])
        rng = np.random.default_rng(config['bootstrap_seed'])
        draws = []
        for start in range(0, config['bootstrap_replicates'], 100):
            samples = rng.integers(len(ordered_ids), size=(min(100,config['bootstrap_replicates']-start),len(ordered_ids)))
            denominators = correct[samples].sum(axis=1)
            keep = denominators > 0
            draws.extend((delta[samples].sum(axis=1)[keep]/denominators[keep]).tolist())
        independent_interval = np.quantile(draws, [0.025,0.975]).tolist()
        assert np.allclose(independent_interval, comparison['ci95'], rtol=0,atol=1e-10)
        independent_ci_checks.append({'target': target,'subset':comparison['subset'],'method_a':comparison['method_a'],
                                       'method_b':comparison['method_b'],'independent_ci95':independent_interval})

# Validate every saved image against the original official data, on CPU.
dataset = CIFAR10(root=str(args.data_root), train=False, download=False, transform=ToTensor())
images = torch.stack([dataset[i][0] for i in ids])
official_labels = torch.tensor([dataset[i][1] for i in ids])
assert all(labels[i] == int(official_labels[pos]) for pos,i in enumerate(ids))
for label in range(10):
    assert sum(labels[i] == label for i in ids) == 100
    assert sum(labels[i] == label for i in subsets['new800']) == 80
artifacts = []
for path in sorted((run/'cache').glob('*.pt')):
    payload = torch.load(path, weights_only=True, map_location='cpu')
    adv = payload['adversarial']
    assert list(payload['ids']) == ids
    torch.testing.assert_close(payload['labels'].cpu(), official_labels, rtol=0,atol=0)
    assert adv.shape == images.shape and adv.dtype == torch.float32
    assert torch.isfinite(adv).all() and float(adv.min()) >= 0 and float(adv.max()) <= 1
    maximum = float((adv-images).abs().max())
    assert maximum <= 8/255 + 1e-6
    stem = path.with_suffix('')
    generation_path = Path(str(stem)+'.generation.json')
    marker = json.loads(Path(str(stem)+'.complete.json').read_text())
    generation = json.loads(generation_path.read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == marker['cache_sha256']
    assert hashlib.sha256(generation_path.read_bytes()).hexdigest() == marker['generation_sha256']
    method = results['methods'][generation['method']]
    assert generation['gradient_evaluations_per_image'] == method['gradient_budget']
    assert generation['sample_view_gradient_evaluations'] == 1000*method['gradient_budget']
    artifacts.append({'path': str(path.relative_to(run)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'max_linf': maximum})
assert len(artifacts) == 25
assert results['total_sample_view_gradient_evaluations'] == 1_130_000
assert sum(job['generation']['sample_view_gradient_evaluations'] for job in results['jobs']) == 1_130_000
assert len(results['comparisons']) == 90

report = {'audit': 'passed', 'model_queries_during_audit': 0, 'attacks_generated_during_audit': 0,
          'metric_implementation_imported': False, 'image_count': 1000, 'pilot_count': 200, 'new_count': 800,
          'prediction_rows': len(rows), 'targets': sorted(clean_by_target), 'method_count': 13,
          'seeded_generation_count': 25, 'summary_rows_checked': 78,
          'comparisons_checked': len(comparison_checks), 'total_sample_view_gradient_evaluations': 1_130_000,
          'paired_point_differences': comparison_checks, 'independently_recomputed_ci': independent_ci_checks,
          'stored_adversarial_artifacts': artifacts,
          'ci_scope': 'All 90 point differences independently recomputed; eight G40 BSR-vs-fixed-step MI confidence intervals independently resampled'}
args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
print(json.dumps({key: value for key,value in report.items() if key not in ('paired_point_differences','stored_adversarial_artifacts')},indent=2))
