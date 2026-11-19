"""Plot paired ASR differences from recorded V1 results; no new experiments."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plot_gains(report):
    report = Path(report).resolve()
    verification = json.loads((report/'verification.json').read_text(encoding='utf-8'))
    if sha256(report/'results.json') != verification['artifacts_sha256']['results.json']:
        raise ValueError('Recorded result checksum mismatch')
    results = json.loads((report/'results.json').read_text(encoding='utf-8'))
    comparisons = {(r['target'],r['subset'],r['method_a'],r['method_b']): r for r in results['comparisons']}
    targets = list(results['targets'])
    names = {'cifar10_mobilenetv2_x1_0':'MobileNetV2','cifar10_vgg11_bn':'VGG11-BN'}
    budgets = (20,40,80)
    all_bounds = [100*x for r in results['comparisons'] if r['subset'] in ('full1000','new800')
                  and r['method_b'].startswith('mi_') for x in r['ci95']]
    lower = min(-5,5*math.floor((min(all_bounds)-1)/5))
    upper = max(5,5*math.ceil((max(all_bounds)+1)/5))
    generated = []
    for subset in ('full1000','new800'):
        fig, axes = plt.subplots(2,2,figsize=(10.8,7.2),sharex=True,sharey=True)
        for row, views in enumerate((2,4)):
            for column, target in enumerate(targets):
                ax = axes[row,column]
                ax.axhline(0,color='#333333',linestyle='--',linewidth=1)
                for suffix,color,marker,label in (
                    ('','#245b93','o','Compared with MI, alpha=eps/T'),
                    ('_fixed_step','#d87822','s','Compared with MI, alpha=eps/10'),
                ):
                    data = [comparisons[(target,subset,f'bsr_m{views}_g{g}',f'mi_g{g}{suffix}')] for g in budgets]
                    ys = [100*r['difference_a_minus_b'] for r in data]
                    errors = [[y-100*r['ci95'][0] for y,r in zip(ys,data)],
                              [100*r['ci95'][1]-y for y,r in zip(ys,data)]]
                    ax.errorbar(budgets,ys,yerr=errors,color=color,marker=marker,linewidth=1.6,
                                capsize=4,markersize=5,label=label)
                ax.set_title(f"{names.get(target,target)} | BSR M={views}",fontsize=11)
                ax.set_ylim(lower,upper)
                ax.set_xticks(budgets)
                ax.grid(alpha=0.2)
                if column == 0:
                    ax.set_ylabel('BSR minus MI ASR (percentage points)',fontsize=9)
                if row == 1:
                    ax.set_xlabel('Gradient evaluations per image, G',fontsize=10)
        fig.suptitle(f'Matched-budget transfer gain | {subset} | BSR: three-seed mean',fontsize=12,y=.985)
        fig.text(.5,.942,'Above zero: BSR higher; below zero: MI higher. Error bars: image-paired 95% bootstrap intervals.',
                 ha='center',fontsize=9)
        handles,labels = axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.045),ncol=2,frameon=False,fontsize=9)
        fig.text(.5,.017,'Conditional on recorded models/seeds; no multiple-comparison correction. Both BSR view counts and MI baselines are shown.',
                 ha='center',fontsize=8)
        fig.subplots_adjust(left=.08,right=.985,top=.875,bottom=.15,wspace=.09,hspace=.21)
        for extension in ('png','svg'):
            filename=f'bsr_gain_vs_budget_{subset}.{extension}'
            fig.savefig(report/filename,dpi=180,bbox_inches='tight',metadata={'Date':None} if extension=='svg' else None)
            generated.append(filename)
        plt.close(fig)
    for filename in generated:
        verification['artifacts_sha256'][filename]=sha256(report/filename)
    verification['gain_visualization']={'renderer':'course_tools/plot_v1_gains.py','sha256':sha256(__file__),
                                      'scope':'Recorded paired differences and confidence intervals; all targets, views, budgets and MI baselines',
                                      'artifacts':generated,'model_queries':0,'attacks_generated':0}
    (report/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'new_figures':generated,'results_sha256':sha256(report/'results.json')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True)
    plot_gains(parser.parse_args().report)
