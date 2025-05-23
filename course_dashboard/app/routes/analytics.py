from flask import Blueprint, request, jsonify
import numpy as np
import pandas as pd
import re
from ..data_loader import load_course_data
import collections

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/top10")
def top10():
    df = load_course_data()
    teach_col = "The instructor's teaching effectiveness is:_mean"

    top = (
        df.nlargest(10, teach_col)
          .loc[:, [
              "course_number",
              "course_name",
              "instructor",
              "year",
              "term",
              teach_col,
              f"{teach_col[:-5]}_n",
          ]]
          .rename(columns={
              teach_col:             "mean",
              f"{teach_col[:-5]}_n": "num_respondents",
              "course_number":       "course_code",
          })
    )

    return jsonify(top.to_dict(orient="records"))


TERM_ORDER = ["Intersession", "Spring", "Summer", "Fall", "Winter"]
TERM_RANK  = {t: i for i, t in enumerate(TERM_ORDER)}
MONTH_FOR_TERM = {
    "Intersession": "01",
    "Spring":       "03",
    "Summer":       "06",
    "Fall":         "09",
    "Winter":       "12",
}
FRAC_FOR_MONTH = {m: TERM_RANK[t] / len(TERM_ORDER)
                  for t, m in MONTH_FOR_TERM.items()}

def term_rank(term: str) -> int:
    """Rank (0‑based) for sorting; unknown terms go last."""
    return TERM_RANK.get(term.strip().title(), len(TERM_ORDER))


def term_to_frac(term: str) -> float:
    """Convert term → fractional offset within a year for regression."""
    return term_rank(term) / len(TERM_ORDER)


def time_key(row: pd.Series) -> str:
    return f"{int(row.year)} {row.term}"


def linear_trend(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    mask = (~np.isnan(xs)) & (~np.isnan(ys))
    if mask.sum() < 2:
        return np.full_like(xs, np.nan, dtype=float)

    m, b = np.polyfit(xs[mask], ys[mask], 1)
    return m * xs + b

def nan2none(lst):
    return [None if pd.isna(v) else v for v in lst]

def clean_instructor(name: str) -> str:
    if pd.isna(name):
        return ""
    txt = str(name).strip()
    txt = re.sub(r"\s+", " ", txt)
    txt = re.sub(r"[.,]\s*$", "", txt)
    return txt

def all_term_dates(frame: pd.DataFrame) -> list[str]:
    dates = (
        frame.assign(
            _date = lambda d:
                d["year"].astype(str) + "-" +
                d["term"].map(lambda t: MONTH_FOR_TERM.get(t, "01")) + "-01"
        )
        ._date.unique()
    )
    return sorted(dates)

def month_frac(date_str: str) -> float:
    return FRAC_FOR_MONTH.get(date_str[5:7], 0.0)

_level_pat = re.compile(r"\.(\d{3})$")

def course_level(code: str) -> float | None:
    m = _level_pat.search(str(code).strip())
    if not m:
        return None
    return (int(m.group(1)) // 100) * 100

@analytics_bp.route("/scatter_json")
def scatter_json():
    df = load_course_data()

    df["instructor"] = df["instructor"].apply(clean_instructor)

    if "course_level" not in df.columns:
        df["course_level"] = df["course_number"].apply(course_level)

    if "size" not in df.columns:
        pat = re.compile(r"\b(\d+)\s+of\s+(\d+)\s+responded", re.I)
        def _size(text: str) -> float | None:
            m = pat.search(str(text));  return float(m.group(2)) if m else None
        meta_col = next((c for c in ("file_name", "filename", "file")
                         if c in df.columns), None)
        if meta_col:
            df["size"] = df[meta_col].apply(_size)

    x_col     = request.args.get("x",  "Compared to other Hopkins courses at this level, the workload for this course is:_mean")
    y_col     = request.args.get("y",  "The instructor's teaching effectiveness is:_mean")
    color_col = request.args.get("color") or None
    year_filt = request.args.get("year")  or None
    term_filt = request.args.get("term")  or None

    cols = [x_col, y_col, "course_level",
            "course_number", "course_name", "instructor", "year", "term"]
    if color_col and color_col not in cols:
        cols.append(color_col)
    cols = list(dict.fromkeys(cols))
    clean   = df[cols].dropna(subset=[x_col, y_col])
    dropped = len(df) - len(clean)

    payload = {
        "x":           clean[x_col].tolist(),
        "y":           clean[y_col].tolist(),
        "course":      clean["course_number"].tolist(),
        "course_name": clean["course_name"].tolist(),
        "instructor":  clean["instructor"].tolist(),
        "year":        clean["year"].astype(int).tolist(),
        "term":        clean["term"].tolist(),
        "metrics": [c for c in df.columns
                    if (c.endswith("_mean")
                        or c in ("size", "course_level"))],
        "warning": (f"{dropped} record(s) excluded because of missing "
                    f"{x_col} / {y_col}") if dropped else ""
    }
    if color_col:
        payload["color"] = clean[color_col].tolist()

    return jsonify(payload)




@analytics_bp.route("/dept_timeseries")
def dept_timeseries():
    df = load_course_data()
    df["instructor"] = df["instructor"].apply(clean_instructor)

    depts  = [d.strip().upper() for d in request.args.get("depts", "").split(",") if d]
    metric = request.args.get(
        "metric", "The instructor's teaching effectiveness is:_mean")
    years  = {int(float(y)) for y in request.args.get("years",  "").split(",") if y}
    terms  = {t.strip().title() for t in request.args.get("terms", "").split(",") if t}

    df["dept"] = df["course_number"].str.split(".").str[0:2].str.join(".")
    if depts:
        df = df[df["dept"].isin(depts)]
    if years:
        df = df[df["year"].fillna(-1).astype(int).isin(years)]
    if terms:
        df = df[df["term"].astype(str).str.strip().str.title().isin(terms)]

    timeline = all_term_dates(df)

    MONTH_TO_FRAC = {m: TERM_RANK[t] / len(TERM_ORDER)
                     for t, m in MONTH_FOR_TERM.items()}

    out = {"metric": metric, "series": [], "timeline": timeline}
    for dept, g in df.groupby(["dept", "year", "term"])[metric].mean().reset_index().groupby("dept"):

        date_map = dict(zip(
            g["year"].astype(str) + "-" +
            g["term"].map(lambda t: MONTH_FOR_TERM.get(t, "01")) + "-01",
            g[metric]
        ))
        ys = np.array([date_map.get(d, np.nan) for d in timeline], dtype=float)

        xs_all = (np.array([int(d[:4]) for d in timeline], dtype=float) +
                  np.array([MONTH_TO_FRAC.get(d[5:7], 0.0) for d in timeline]))

        mask = ~np.isnan(ys)
        if mask.sum() >= 2:
            m, b      = np.polyfit(xs_all[mask], ys[mask], 1)
            trend_all = m * xs_all + b
        else:
            trend_all = np.full_like(xs_all, np.nan, dtype=float)

        out["series"].append({
            "label": dept,
            "x":     timeline,
            "y":     nan2none(ys.tolist()),
            "trend": nan2none(trend_all.tolist())
        })

    return jsonify(out)


@analytics_bp.route("/course_timeseries")
def course_timeseries():
    df = load_course_data()
    df["instructor"] = df["instructor"].apply(clean_instructor)

    code = request.args.get("course")
    if not code:
        return jsonify({"error": "course parameter is required"}), 400

    metric = request.args.get(
        "metric", "The instructor's teaching effectiveness is:_mean")
    years  = {int(float(y)) for y in request.args.get("years",  "").split(",") if y}
    terms  = {t.strip().title() for t in request.args.get("terms", "").split(",") if t}

    df = df[df["course_number"].str.upper() == code.upper()]
    if years:
        df = df[df["year"].fillna(-1).astype(int).isin(years)]
    if terms:
        df = df[df["term"].astype(str).str.strip().str.title().isin(terms)]

    timeline = all_term_dates(df)
    MONTH_TO_FRAC = {m: TERM_RANK[t] / len(TERM_ORDER)
                     for t, m in MONTH_FOR_TERM.items()}

    out = {"metric": metric, "series": [], "timeline": timeline}
    for instr, g in df.groupby(["instructor", "year", "term"])[metric].mean().reset_index().groupby("instructor"):

        date_map = dict(zip(
            g["year"].astype(str) + "-" +
            g["term"].map(lambda t: MONTH_FOR_TERM.get(t, "01")) + "-01",
            g[metric]
        ))
        ys = np.array([date_map.get(d, np.nan) for d in timeline], dtype=float)

        xs_all = (np.array([int(d[:4]) for d in timeline], dtype=float) +
                  np.array([MONTH_TO_FRAC.get(d[5:7], 0.0) for d in timeline]))

        mask = ~np.isnan(ys)
        if mask.sum() >= 2:
            m, b      = np.polyfit(xs_all[mask], ys[mask], 1)
            trend_all = m * xs_all + b
        else:
            trend_all = np.full_like(xs_all, np.nan, dtype=float)

        out["series"].append({
            "label": instr,
            "x":     timeline,
            "y":     nan2none(ys.tolist()),
            "trend": nan2none(trend_all.tolist())
        })

    return jsonify(out)

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.cluster import DBSCAN
import joblib


def _fit_embedding(X: pd.DataFrame, qp: dict[str, str]) -> np.ndarray:
    method = qp.get("method", "pca").lower()
    X_std  = StandardScaler().fit_transform(X)
    if method == "tsne":
        params = dict(perplexity=float(qp.get("perplexity", 30)),
                      n_iter=int(qp.get("n_iter", 1000)),
                      random_state=0)
        return TSNE(n_components=2, **params).fit_transform(X_std)
    return PCA(n_components=2, random_state=0).fit_transform(X_std)

def _dbscan_labels(emb, qp):
    return DBSCAN(
        eps=float(qp.get("eps", 2.0)),
        min_samples=int(qp.get("min_samples", 5)),
    ).fit_predict(emb)

@analytics_bp.route("/course_embedding")
def course_embedding():
    df       = load_course_data()
    metrics  = [c for c in df.columns if c.endswith("_mean")]
    X        = df[metrics].dropna()
    meta     = df.loc[X.index, ["course_number", "course_name",
                                "instructor", "year", "term"]]
    cache    = joblib.Memory("/tmp/jhu_eval_cache", verbose=0)
    emb      = cache.cache(_fit_embedding)(X, request.args)

    payload = {
        "x"   : emb[:, 0].tolist(),
        "y"   : emb[:, 1].tolist(),
        "course"    : meta.course_number.tolist(),
        "name"      : meta.course_name.tolist(),
        "dept"      : meta.course_number.str.split('.').str[0:2].str.join('.').tolist(),
        "level"     : meta.course_number.str.extract(r'\.(\d)').iloc[:,0].fillna('').tolist(),
        "instructor": meta.instructor.tolist(),
        "year"      : meta.year.astype(int).tolist(),
        "term"      : meta.term.tolist()
    }

    if request.args.get("cluster") == "dbscan":
        labels = _dbscan_labels(emb, request.args)
        payload["cluster"] = labels.tolist()

        clust_stats = collections.defaultdict(list)
        for lbl, row in zip(labels, meta.itertuples()):
            if lbl < 0:
                continue
            clust_stats[lbl].append(row.course_number)
        payload["cluster_stats"] = {int(k): v for k, v in clust_stats.items()}
        level = (
            meta.course_number
                .str.extract(r'\.(\d{3})$')[0]
                .astype('Int64')
                .floordiv(100)
        )
        payload["level"] = level.tolist()

    return jsonify(payload)

@analytics_bp.route("/cluster_summary")
def cluster_summary():
    """
    Either:
      /cluster_summary?courses=AS.020.101,…
    or
      /cluster_summary?cluster=7&method=tsne&eps=2.0  (re-runs DBSCAN server-side)
    """
    df       = load_course_data()
    metrics  = [c for c in df.columns if c.endswith("_mean")]

    if 'cluster' in request.args:
        qp   = request.args.to_dict()
        X    = df[metrics].dropna()
        emb  = _fit_embedding(X, qp)
        lbls = _dbscan_labels(emb, qp)
        target = int(qp['cluster'])
        mask   = lbls == target
        sub    = df.loc[X.index[mask]]
    else:
        courses = [c.strip() for c in request.args.get("courses", "").split(',') if c]
        sub     = df[df.course_number.isin(courses)]

    if sub.empty:
        return jsonify({"error":"no data"}), 400

    out = {
        "n_courses"    : int(sub.course_number.nunique()),
        "top_departments" : (sub.course_number.str.split('.').str[0:2]
                             .str.join('.').value_counts().head(3).index.tolist()),
        "mean_effectiveness" : round(sub["The instructor's teaching effectiveness is:_mean"].mean(), 2),
        "mean_workload"      : round(sub["Compared to other Hopkins courses at this level, the workload for this course is:_mean"].mean(), 2)
    }
    out["metrics"] = sub[metrics].mean().round(2).to_dict()
    return jsonify(out)

@analytics_bp.route("/recommend")
def recommend():
    df       = load_course_data()
    metrics  = [c for c in df.columns if c.endswith("_mean")]

    code  = request.args.get("course", "").strip()
    year  = request.args.get("year")
    term  = request.args.get("term")

    mask = df.course_number.str.upper() == code.upper()
    if year:
        mask &= df["year"].fillna(-1).astype(int) == int(year)
    if term:
        mask &= df["term"].astype(str).str.strip().str.title() == term.strip().title()
    if not mask.any():
        return jsonify([])

    X      = df[metrics].dropna()
    emb    = _fit_embedding(X, request.args)
    labels = _dbscan_labels(emb, request.args)

    target_idx  = set(df[mask].index)
    target_lbls = {lbl for i, lbl in zip(X.index, labels) if i in target_idx}
    if not target_lbls or -1 in target_lbls:
        return jsonify([])

    lbl         = target_lbls.pop()
    rec_idx     = [i for i, l in zip(X.index, labels)
                   if l == lbl and i not in target_idx]
    sub = df.loc[rec_idx,
             ["course_number", "course_name",
              "instructor", "year", "term"]]
    sub = sub[sub.course_number.str.upper() != code.upper()]
    sub = (sub
       .sort_values(["course_number", "year", "term"])
       .drop_duplicates(subset=["course_number", "year", "term"],
                        keep="first"))
    sub = sub.drop_duplicates()

    return jsonify(sub.to_dict(orient="records"))