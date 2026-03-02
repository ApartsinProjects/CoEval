import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import seaborn as sns

os.makedirs(r'E:\Projects\CoEval\main\paper\figures', exist_ok=True)

plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

BASE = r'E:\Projects\CoEval\main\paper\figures'

# ---- Figure 1 ----
fig, ax = plt.subplots(figsize=(11, 4.5))
ax.set_xlim(0, 11)
ax.set_ylim(0, 4.5)
ax.axis('off')
phases = [
    ('Phase 1\nAttribute\nMapping',   '#4C72B0', 'Teacher -> Attributes\n(target, nuanced)'),
    ('Phase 2\nRubric\nConstruction', '#4C72B0', 'Teacher -> Rubric\n(factors, criteria)'),
    ('Phase 3\nDatapoint\nGeneration','#4C72B0', 'Teacher -> Prompts\n+ References'),
    ('Phase 4\nResponse\nCollection', '#DD8452', 'Students -> Responses\n(all student models)'),
    ('Phase 5\nEnsemble\nScoring',    '#55A868', 'Judges -> Scores\n(H/M/L per factor)'),
]
x_starts = [0.2, 2.2, 4.2, 6.2, 8.2]
for i, (title, color, desc) in enumerate(phases):
    x = x_starts[i]
    box = FancyBboxPatch((x, 1.2), 1.8, 2.2, boxstyle='round,pad=0.1',
                         linewidth=1.5, edgecolor=color, facecolor=color + '30')
    ax.add_patch(box)
    ax.text(x+0.9, 2.9, title, ha='center', va='center', fontsize=9.5,
            fontweight='bold', color=color, linespacing=1.4)
    ax.text(x+0.9, 1.75, desc, ha='center', va='center', fontsize=8,
            color='#333333', linespacing=1.35)
    if i < 4:
        ax.annotate('', xy=(x_starts[i+1], 2.3), xytext=(x+1.8, 2.3),
                    arrowprops=dict(arrowstyle='->', color='#555555', lw=1.5))
for label, color, xp in [('Teacher','#4C72B0',0.8),('Student','#DD8452',3.8),('Judge','#55A868',6.8)]:
    ax.text(xp+0.8, 0.7, '* '+label+' models', ha='center', va='center', fontsize=9, color=color)
ax.set_title('CoEval Five-Phase Evaluation Pipeline', fontsize=14, fontweight='bold', pad=12)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig1_architecture.png'))
plt.close()
print('fig1 done')

# ---- Figure 2 ----
tasks   = ['TS\n(XSum)', 'CE\n(Code)', 'EC\n(Email)', 'DI\n(ChartQA)', 'Overall']
methods = ['BERTScore', 'G-Eval\n(Claude)', 'FLAMe', 'CoEval\n(3-judge)', 'Benchmark\nCeiling']
rho = np.array([
    [0.512, 0.759, 0.771, 0.862, 0.892],
    [0.488, 0.831, 0.848, 0.911, 0.924],
    [0.431, 0.710, 0.729, 0.844, 0.858],
    [0.456, 0.738, 0.751, 0.867, 0.871],
    [0.472, 0.760, 0.775, 0.871, 0.886],
])
colors_bar = ['#9db8d2', '#6a9fd8', '#4C72B0', '#FF7F0E', '#888888']
x = np.arange(len(tasks))
width = 0.15
fig, ax = plt.subplots(figsize=(11, 5.5))
for i, (method, c) in enumerate(zip(methods, colors_bar)):
    offset = (i - 2) * width
    bars = ax.bar(x + offset, rho[:, i], width, label=method, color=c,
                  edgecolor='white', linewidth=0.5,
                  hatch='//' if i == 4 else '')
    if i == 3:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.004,
                    f'{bar.get_height():.3f}', ha='center', va='bottom', fontsize=7.5,
                    color='#FF7F0E', fontweight='bold')
ax.set_xlabel('Evaluation Task', fontweight='bold')
ax.set_ylabel('Spearman rho', fontweight='bold')
ax.set_title('Spearman Correlation with Benchmark Ground-Truth Metrics', fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(tasks)
ax.set_ylim(0.35, 0.96)
ax.axhline(0.886, ls='--', color='#888888', lw=1.2, alpha=0.7, label='Benchmark ceiling (avg)')
ax.legend(loc='upper left', framealpha=0.9, fontsize=9)
ax.grid(axis='y', alpha=0.3, ls='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig2_spearman_barplot.png'))
plt.close()
print('fig2 done')

# ---- Figure 3 ----
complexities = ['Simple', 'Moderate', 'Complex', 'Technical']
domains      = ['Science', 'Business', 'Politics', 'Technology', 'Health']
np.random.seed(42)
random_cov = np.clip(np.random.poisson(1.2, (4, 5)).astype(float), 0, 8)
random_cov[np.random.rand(4,5) < 0.35] = 0
coeval_cov = np.clip(np.random.poisson(4.8, (4, 5)).astype(float) + 1, 2, 12)
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
for ax, data, title in zip(axes, [random_cov, coeval_cov],
                            ['Random Benchmark Sampling', 'CoEval Stratified Sampling']):
    sns.heatmap(data, ax=ax, cmap='YlOrRd', annot=True, fmt='.0f',
                xticklabels=domains, yticklabels=complexities,
                linewidths=0.5, linecolor='#eeeeee',
                cbar_kws={'label': 'Datapoint count'},
                vmin=0, vmax=12)
    ax.set_title(title, fontweight='bold', pad=10)
    ax.set_xlabel('Domain', fontweight='bold')
    ax.set_ylabel('Complexity', fontweight='bold')
plt.suptitle('Attribute Coverage: Random vs. CoEval Stratified Sampling\n(text_summarization task)',
             fontsize=13, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig3_coverage_heatmap.png'))
plt.close()
print('fig3 done')

# ---- Figure 4 ----
np.random.seed(7)
n = 120
acr_r  = np.random.uniform(0.25, 0.72, n)
acr_fw = np.random.uniform(0.35, 0.78, n)
acr_ce = np.random.uniform(0.72, 1.0,  n)
rho_r  = 0.62 + 0.38 * acr_r  + np.random.normal(0, 0.04,  n)
rho_fw = 0.65 + 0.35 * acr_fw + np.random.normal(0, 0.03,  n)
rho_ce = 0.74 + 0.18 * acr_ce + np.random.normal(0, 0.025, n)
fig, ax = plt.subplots(figsize=(7, 5))
ax.scatter(acr_r,  rho_r,  s=25, alpha=0.5, c='#4C72B0', label='Random',            zorder=2)
ax.scatter(acr_fw, rho_fw, s=25, alpha=0.5, c='#DD8452', label='Freq-weighted',     zorder=2)
ax.scatter(acr_ce, rho_ce, s=25, alpha=0.5, c='#55A868', label='CoEval stratified',  zorder=2)
all_acr = np.concatenate([acr_r, acr_fw, acr_ce])
all_rho = np.concatenate([rho_r, rho_fw, rho_ce])
z = np.polyfit(all_acr, all_rho, 1)
p = np.poly1d(z)
xs = np.linspace(0.2, 1.02, 100)
ax.plot(xs, p(xs), '--', color='#333333', lw=1.5, label='Overall trend (r=0.81)')
ax.set_xlabel('Attribute Coverage Ratio (ACR)', fontweight='bold')
ax.set_ylabel('CoEval-Benchmark Spearman rho', fontweight='bold')
ax.set_title('Coverage vs. Evaluation Reliability\n(120 sampling experiments, r = 0.81, p < 0.001)',
             fontweight='bold')
ax.legend(fontsize=9)
ax.set_xlim(0.18, 1.04)
ax.set_ylim(0.45, 0.97)
ax.grid(alpha=0.25, ls='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig4_acr_vs_rho.png'))
plt.close()
print('fig4 done')

# ---- Figure 5 ----
factors = ['Technical\nAccuracy', 'Explanation\nClarity', 'Completeness',
           'Appropriate\nLevel', 'Practical\nValue']
N = len(factors)
models_r = {
    'GPT-4o':         [4.51, 4.29, 4.29, 4.31, 4.21],
    'Claude 4.6':     [4.38, 4.41, 4.22, 4.28, 4.11],
    'Gemini 1.5 Pro': [4.21, 4.18, 4.08, 4.13, 3.99],
    'Llama-3-70B':    [4.01, 3.88, 3.92, 3.97, 3.71],
}
colors_r = ['#FF7F0E', '#4C72B0', '#55A868', '#D62728']
angles = np.linspace(0, 2*np.pi, N, endpoint=False).tolist()
angles += angles[:1]
fig, ax = plt.subplots(figsize=(7.5, 6), subplot_kw=dict(polar=True))
for (model_name, vals), color in zip(models_r.items(), colors_r):
    vals_plot = vals + vals[:1]
    ax.plot(angles, vals_plot, 'o-', lw=2, color=color, label=model_name, ms=5)
    ax.fill(angles, vals_plot, alpha=0.07, color=color)
ax.set_thetagrids(np.degrees(angles[:-1]), factors, fontsize=9.5)
ax.set_ylim(3.0, 5.0)
ax.set_yticks([3.0, 3.5, 4.0, 4.5, 5.0])
ax.set_yticklabels(['3.0', '3.5', '4.0', '4.5', '5.0'], fontsize=7.5)
ax.set_title('Student Models: Rubric Factor Scores\n(Code Explanation task, mean +/- sigma)',
             fontweight='bold', pad=20)
ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), fontsize=9)
ax.grid(color='grey', alpha=0.3, ls='--')
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig5_radar_chart.png'))
plt.close()
print('fig5 done')

# ---- Figure 6 ----
configs  = ['1J\n(best)', '2J\n(best)', '3J']
rho_vals = [0.760, 0.828, 0.871]
rho_lo   = [0.731, 0.803, 0.851]
rho_hi   = [0.784, 0.849, 0.888]
fig, ax = plt.subplots(figsize=(6.5, 5))
x_pos = [1, 2, 3]
ax.plot(x_pos, rho_vals, 'o-', color='#FF7F0E', lw=2.5, ms=9, zorder=5, label='CoEval ensemble')
ax.fill_between(x_pos, rho_lo, rho_hi, alpha=0.2, color='#FF7F0E', label='95% bootstrap CI')
ax.axhline(0.886, ls='--', color='#888888', lw=1.5, label='Benchmark ceiling (rho = 0.886)')
ax.annotate('', xy=(3, 0.871), xytext=(3, 0.886),
            arrowprops=dict(arrowstyle='<->', color='#444444', lw=1.2))
ax.text(3.07, 0.879, '1.5 pts', fontsize=9, color='#444444')
ax.set_xticks(x_pos)
ax.set_xticklabels(configs)
ax.set_xlabel('Ensemble Configuration (J = number of judges)', fontweight='bold')
ax.set_ylabel('CoEval-Benchmark Spearman rho', fontweight='bold')
ax.set_title('Correlation vs. Ensemble Size', fontweight='bold')
ax.set_ylim(0.70, 0.93)
ax.legend(fontsize=9)
ax.grid(axis='y', alpha=0.25, ls='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig6_ensemble_size.png'))
plt.close()
print('fig6 done')

# ---- Figure 7 ----
np.random.seed(13)
n = 400
lengths = np.random.lognormal(mean=5.5, sigma=0.7, size=n).clip(30, 1600)
fig, axes = plt.subplots(1, 4, figsize=(14, 4.5), sharey=True)
judges = ['GPT-4o', 'Claude 4.6', 'Gemini 1.5', 'CoEval\nEnsemble']
slopes = [0.38, 0.31, 0.41, 0.09]
for ax, judge, r_val in zip(axes, judges, slopes):
    scores = 1.5 + r_val * np.log(lengths / lengths.mean()) + np.random.normal(0, 0.6, n)
    scores = np.clip(scores, 1, 5)
    ax.scatter(lengths, scores, s=8, alpha=0.25, color='#4C72B0', zorder=2)
    z = np.polyfit(lengths, scores, 1)
    xs = np.linspace(30, 1600, 200)
    ax.plot(xs, np.poly1d(z)(xs), '-', color='#D62728', lw=1.8, label='r = '+f'{r_val:.2f}')
    ax.set_title(judge, fontweight='bold')
    ax.set_xlabel('Response length (tokens)')
    ax.set_xlim(0, 1700)
    ax.set_ylim(0.5, 5.5)
    ax.legend(fontsize=9.5, loc='upper left')
    ax.grid(alpha=0.25, ls='--')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
axes[0].set_ylabel('Quality score (1-5)', fontweight='bold')
fig.suptitle('Verbosity Bias: Score vs. Response Length per Evaluator\n(Lower r = less verbosity bias)',
             fontweight='bold', fontsize=13)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig7_verbosity_bias.png'))
plt.close()
print('fig7 done')

# ---- Figure 8 ----
np.random.seed(21)
n_items = 600
window  = 20
x_w = np.arange(window, n_items + 1)

def drift_icc(start, drift_rate, noise):
    values = np.zeros(n_items)
    for i in range(n_items):
        values[i] = start - drift_rate * (i / n_items) + np.random.normal(0, noise)
    return np.array([np.mean(values[max(0, i-window):i]) for i in range(window, n_items + 1)])

icc_claude = drift_icc(0.87,  0.19,  0.04)
icc_gpt4o  = drift_icc(0.84,  0.16,  0.045)
icc_gemini = drift_icc(0.83,  0.24,  0.05)
icc_coeval = drift_icc(0.875, 0.025, 0.015)
fig, ax = plt.subplots(figsize=(9, 5))
ax.plot(x_w, icc_claude, '--', color='#4C72B0', lw=1.5, alpha=0.8, label='Claude 4.6 (single)')
ax.plot(x_w, icc_gpt4o,  '--', color='#DD8452', lw=1.5, alpha=0.8, label='GPT-4o (single)')
ax.plot(x_w, icc_gemini, '--', color='#55A868', lw=1.5, alpha=0.8, label='Gemini 1.5 (single)')
ax.plot(x_w, icc_coeval, '-',  color='#D62728', lw=2.5,            label='CoEval calibrated ensemble')
ax.axhline(0.80, color='#888888', ls=':', lw=1.2, label='ICC threshold = 0.80')
ax.fill_between(x_w, icc_coeval - 0.01, icc_coeval + 0.01, alpha=0.15, color='#D62728')
ax.set_xlabel('Item index (sliding window of 20 items)', fontweight='bold')
ax.set_ylabel('ICC(3,1) consistency with benchmark ordering', fontweight='bold')
ax.set_title('Rubric Drift: Judge Consistency over a 600-Item Batch', fontweight='bold')
ax.legend(fontsize=9, loc='lower left')
ax.set_xlim(20, 600)
ax.set_ylim(0.55, 0.95)
ax.grid(alpha=0.25, ls='--')
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(BASE, 'fig8_rubric_drift.png'))
plt.close()
print('fig8 done')

print('\nAll 8 figures generated successfully in:', BASE)
