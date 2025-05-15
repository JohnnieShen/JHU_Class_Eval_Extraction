import pandas as pd, ast, numpy as np
import os

PARSED_PATH = os.path.join(
    os.path.dirname(__file__),
    'data',
    'course_stats_parsed.feather'
)

def _load_df():
    return pd.read_feather(PARSED_PATH)

_df = _load_df()

def load_course_data():
    return _df