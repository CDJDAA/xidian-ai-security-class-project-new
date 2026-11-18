from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.font_manager import FontProperties
repo=Path(__file__).resolve().parents[5];dest=repo/'projects/multi-agent-security-research/manuscripts/2026-11-18-source-grounding'
figdir=dest/'figures';figdir.mkdir(exist_ok=True)
font=FontProperties(fname='C:/Windows/Fonts/simsun.ttc')
plt.rcParams.update({'font.family':font.get_name(),'font.size':10,'axes.unicode_minus':False,'savefig.facecolor':'white'})

fig,ax=plt.subplots(figsize=(10,5.8));ax.set(xlim=(0,10),ylim=(0,5.8));ax.axis('off')
def box(x,y,w,h,text,fc='#f1f4f6'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.04,rounding_size=0.06',facecolor=fc,edgecolor='#293943',linewidth=1))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontproperties=font,fontsize=13)
def arrow(a,b):ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,color='#293943',linewidth=1.1))
box(.1,4.5,2.05,.85,'任务 01 文献获取\n版本与响应哈希')
box(2.65,4.5,2.05,.85,'任务 02 实验审核\n计数与解释边界')
box(5.2,4.5,2.05,.85,'任务 04 证据绑定\n原文与摘录匹配')
box(7.75,4.5,2.05,.85,'任务 03 引用保存\n编号与存在性')
ax.text(5,5.65,'四项目独立模块的证据职责',ha='center',fontproperties=font,fontsize=15)
ax.add_patch(Rectangle((.1,1.55),9.7,2.45,fill=False,linestyle='--',edgecolor='#505050',linewidth=1))
ax.text(.3,3.78,'三角色原型：固定来源快照，每轮重新核验',ha='left',fontproperties=font,fontsize=14)
box(.4,2.3,1.5,.8,'阅读角色\n候选结论')
box(2.1,2.3,1.2,.8,'程序核验\nV(c)')
box(3.5,2.3,1.5,.8,'分析角色\n候选结论')
box(5.2,2.3,1.2,.8,'程序核验\nV(c)')
box(6.6,2.3,1.5,.8,'核验角色\n候选结论')
box(8.3,2.3,1.2,.8,'程序核验\nV(c)')
for x in [1.9,3.3,5.0,6.4,8.1]:arrow((x,2.7),(x+.2,2.7))
ax.text(5,1.85,'只对被核验的结论字段给出来源匹配状态',ha='center',fontproperties=font,fontsize=13)
box(.4,.3,4.3,.85,'sources：原始资料，仍不可信\n可包含攻击文本，保留用于复核',fc='white')
box(5.2,.3,4.3,.85,'citations：匹配摘录，不等于安全指令\n未核验 topics 不进入受限证据包',fc='white')
fig.tight_layout(pad=.4);fig.savefig(figdir/'workflow.png',dpi=220);plt.close(fig)

d=json.loads((repo/'projects/multi-agent-security-research/experiments/source_tracking/boundary-probe-20261118.json').read_text(encoding='utf-8'))
fig,ax=plt.subplots(figsize=(7.2,6.8));fig.subplots_adjust(left=.45,right=.98,top=.9,bottom=.04)
ax.set_xlim(-.5,1.5);ax.set_ylim(17.5,-.5)
ax.set_xticks([0,1],['直接 ID','程序序号']);ax.xaxis.tick_top()
labels=[f"{i+1:02}  {r['label']}" for i,r in enumerate(d['cases'])]
ax.set_yticks(range(18),labels,fontproperties=font,fontsize=11)
ax.tick_params(axis='both',length=0,pad=10)
for i,row in enumerate(d['cases']):
    for j,name in enumerate(['strict_id','bound_index']):
        val=row['outcomes'][name]['accepted']
        ax.add_patch(Rectangle((j-.48,i-.46),.96,.92,facecolor='#d8e4ea' if val else 'white',edgecolor='#808080',linewidth=.65))
        s=str(val)+('*' if row['case_id']=='stale_common' and name=='bound_index' else '')
        ax.text(j,i,s,ha='center',va='center',fontsize=12,fontweight='bold')
for spine in ax.spines.values():spine.set_visible(False)
fig.savefig(figdir/'probe-matrix.png',dpi=220);plt.close(fig)
print('Saved two manuscript figures from code roles and recorded probe results.')
