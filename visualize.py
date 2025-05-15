import pandas as pd
import ast
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

import pandas as pd
import ast
import numpy as np
import matplotlib.pyplot as plt

df = pd.read_csv('all_course_stats.csv')
hist_cols = df.columns[7:]

def parse_hist_stats(cell):
    if pd.isna(cell):
        return 0, np.nan, np.nan
    pairs = ast.literal_eval(cell)
    counts = {v: c for v, c in pairs if v != 0}
    n = sum(counts.values())
    if n == 0:
        return 0, np.nan, np.nan
    mean = sum(v*c for v,c in counts.items()) / n
    m2 = sum((v**2)*c for v,c in counts.items()) / n
    var = m2 - mean**2
    sd = np.sqrt(var) if var > 0 else 0.0
    return n, mean, sd

for q in hist_cols:
    df[[f'{q}_n', f'{q}_mean', f'{q}_sd']] = df[q].apply(
        lambda cell: pd.Series(parse_hist_stats(cell))
    )
    df[f'{q}_stderr']  = df[f'{q}_sd']   / np.sqrt(df[f'{q}_n'])
    df[f'{q}_ci_lower'] = df[f'{q}_mean'] - 1.96 * df[f'{q}_stderr']
    df[f'{q}_ci_upper'] = df[f'{q}_mean'] + 1.96 * df[f'{q}_stderr']

course_col = df.columns[0]
instr_col  = next(c for c in df.columns if 'instructor' in c.lower())
year_col   = next(c for c in df.columns if 'year' in c.lower())
term_col   = next(c for c in df.columns if 'term' in c.lower())
teach_q    = hist_cols[0]
work_q     = hist_cols[-1]
teach_mean = f'{teach_q}_mean'
work_mean  = f'{work_q}_mean'

top10    = df.nlargest(10, teach_mean)[[course_col, instr_col, teach_mean, f'{teach_q}_n']]
bottom10 = df.nsmallest(10, teach_mean)[[course_col, instr_col, teach_mean, f'{teach_q}_n']]
print("Top 10 Courses by Teaching Effectiveness\n",  top10,  "\n")
print("Bottom 10 Courses by Teaching Effectiveness\n", bottom10, "\n")

teach_med = df[teach_mean].median()
work_med  = df[work_mean] .median()
plt.figure(figsize=(8,6))
plt.scatter(df[work_mean], df[teach_mean], alpha=0.6)
plt.axvline(work_med, linestyle='--')
plt.axhline(teach_med, linestyle='--')
plt.xlabel(f"{work_q} mean")
plt.ylabel(f"{teach_q} mean")
plt.title("Quadrants: Hard & Loved vs Easy & Disliked")
plt.tight_layout()
plt.show()

mask = df[[work_mean, teach_mean]].notnull().all(axis=1)
x = df.loc[mask, work_mean].values
y = df.loc[mask, teach_mean].values
m, b = np.polyfit(x, y, 1)
y_pred = m*x + b
ss_res = np.sum((y - y_pred)**2)
ss_tot = np.sum((y - y.mean())**2)
r2     = 1 - ss_res/ss_tot

plt.figure(figsize=(8,6))
plt.scatter(x, y, alpha=0.5)
plt.plot(x, y_pred, color='r')
plt.text(0.05, 0.95, f"$R^2$ = {r2:.2f}", transform=plt.gca().transAxes,
         va='top')
plt.xlabel(f"{work_q} mean")
plt.ylabel(f"{teach_q} mean")
plt.title("Trend: Workload vs Teaching Effectiveness")
plt.tight_layout()
plt.show()

median_teach = df[teach_mean].median()
df['dept'] = df[course_col].str.extract(r'^([A-Za-z]+)', expand=False)
league = (
    df.groupby(instr_col)
      .apply(lambda d: pd.Series({
          'weighted_mean':    np.average(d[teach_mean], weights=d[f'{teach_q}_n']),
          '% above median':   100 * np.mean(d[teach_mean] > median_teach),
          'total_responses':  d[f'{teach_q}_n'].sum(),
          'courses_count':    len(d)
      }))
      .reset_index()
      .sort_values('weighted_mean', ascending=False)
)
print("Instructor League Table (Top 20)\n", league.head(20), "\n")

plt.figure(figsize=(8,4))
yearly = df.groupby(year_col)[work_mean].mean()
plt.plot(yearly.index, yearly.values, marker='o')
plt.xlabel("Year")
plt.ylabel("Avg Workload Mean")
plt.title("Workload Trend Over Years")
plt.tight_layout()
plt.show()

plt.figure(figsize=(8,4))
termly = df.groupby([year_col, term_col])[work_mean].mean().unstack(term_col)
for term in termly.columns:
    plt.plot(termly.index, termly[term], marker='o', label=term)
plt.xlabel("Year")
plt.ylabel("Avg Workload Mean")
plt.title("Workload Trend by Term")
plt.legend()
plt.tight_layout()
plt.show()

top10_df = df.nlargest(10, teach_mean).set_index(course_col)
plt.figure(figsize=(10,5))
plt.errorbar(
    x=np.arange(len(top10_df)),
    y=top10_df[teach_mean],
    yerr=1.96 * top10_df[f'{teach_q}_stderr'],
    fmt='o'
)
plt.xticks(np.arange(len(top10_df)), top10_df.index, rotation=45, ha='right')
plt.ylabel("Teaching Effectiveness Mean (95% CI)")
plt.title("Top 10 Courses with 95% CI")
plt.tight_layout()
plt.show()
