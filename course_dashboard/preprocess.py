import pandas as pd
import ast
import numpy as np
import os

RAW_PATH = os.path.join(
    os.path.dirname(__file__),
    'app',
    'data',
    'all_course_stats.csv'
)
df = pd.read_csv(RAW_PATH)

hist_cols = df.columns[7:]

def parse_hist_stats(cell):
    if pd.isna(cell):
        return 0, np.nan
    pairs = ast.literal_eval(cell)
    counts = {v: c for v, c in pairs if v != 0}
    n = sum(counts.values())
    mean = sum(v*c for v,c in counts.items())/n if n else np.nan
    return n, mean

for col in hist_cols:
    df[[f'{col}_n', f'{col}_mean']] = df[col].apply(
        lambda cell: pd.Series(parse_hist_stats(cell))
    )

df = df.drop(columns=hist_cols)

PKL_OUT = os.path.join(
    os.path.dirname(__file__),
    'app',
    'data',
    'course_stats_parsed.pkl'
)
FEATHER_OUT = os.path.join(
    os.path.dirname(__file__),
    'app',
    'data',
    'course_stats_parsed.feather'
)

df.to_pickle(PKL_OUT)
df.reset_index(drop=True).to_feather(FEATHER_OUT)

print(f"Preprocessed {len(df)} rows →\n  • Pickle:   {PKL_OUT}\n  • Feather: {FEATHER_OUT}")
