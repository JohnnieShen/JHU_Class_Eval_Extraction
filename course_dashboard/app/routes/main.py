from flask import Blueprint, render_template
from ..data_loader import load_course_data

main_bp = Blueprint("main", __name__)

@main_bp.route("/")
def index():
    df = load_course_data()

    summary = {
        "Teaching mean": round(
            df["The instructor's teaching effectiveness is:_mean"].mean(), 3
        ),
        "Workload mean": round(
            df[
                "Compared to other Hopkins courses at this level, the workload for this course is:_mean"
            ].mean(),
            3,
        ),
        "Courses total": len(df),
    }

    years = sorted(df["year"].dropna().astype(int).unique().tolist())
    terms = sorted(df["term"].dropna().unique().tolist())

    return render_template(
        "index.html",
        summary=summary,
        years=years,
        terms=terms,
    )
