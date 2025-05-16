from flask import Blueprint, render_template, request
from app.data_loader import load_course_data
from app.routes.helper import parse_term, summarize_trend, DEPT_CODES
import pandas as pd
import re

rec_bp = Blueprint("recommend", __name__)

@rec_bp.route("/recommend", methods=["GET", "POST"])
def recommend():
    df = load_course_data()
    df.columns = df.columns.str.strip()

    if "term" in df.columns and "year" in df.columns:
        df[["term_date", "term_label"]] = df.apply(
            lambda row: pd.Series(parse_term(row["term"], row["year"])), axis=1
        )
    else:
        df["term_date"] = pd.NaT
        df["term_label"] = "Unknown"

    results = []
    filter_type = request.form.get("filter_type") if request.method == "POST" else None
    filtered_df = df.copy()

    if request.method == "POST":
        selected_course = request.form.get("course_number")
        selected_professor = request.form.get("instructor")
        selected_level = request.form.get("level")

        if filter_type == "course" and selected_course:
            filtered_df = filtered_df[filtered_df["course_number"] == selected_course]

        if filter_type == "professor" and selected_professor:
            filtered_df = filtered_df[filtered_df["instructor"] == selected_professor]

        if filter_type == "level" and selected_level:
            def extract_level(code):
                match = re.match(r".*?(\d{3})$", code)
                if match:
                    return match.group(1)[0] + "00"
                return None

            df["course_level"] = df["course_number"].dropna().apply(extract_level)
            filtered_df = df[df["course_level"] == selected_level]

        if not filtered_df.empty:
            grouped = filtered_df.groupby(
                ["course_number", "course_name", "instructor"], as_index=False
            ).agg({
                "The instructor's teaching effectiveness is:_mean": "mean",
                "The intellectual challenge of this course is:_mean": "mean",
                "Compared to other Hopkins courses at this level, the workload for this course is:_mean": "mean",
                "num_respondents": "sum",
            })

            grouped = grouped[grouped["num_respondents"] >= 5]
            grouped = grouped.sort_values(
                by=[
                    "The instructor's teaching effectiveness is:_mean",
                    "The intellectual challenge of this course is:_mean",
                ],
                ascending=[False, False],
            )

            for _, row in grouped.iterrows():
                subset = filtered_df[
                    (filtered_df["course_number"] == row["course_number"]) &
                    (filtered_df["instructor"] == row["instructor"])
                ]
                scores = subset["The instructor's teaching effectiveness is:_mean"].dropna().tolist()
                dates = subset["term_date"].dropna().tolist()
                trend_summary = summarize_trend(scores, dates)

                results.append({
                    "course_number": row["course_number"],
                    "course_name": row["course_name"],
                    "instructor": row["instructor"],
                    "teaching_score": round(row["The instructor's teaching effectiveness is:_mean"], 2),
                    "challenge_score": round(row["The intellectual challenge of this course is:_mean"], 2),
                    "workload_score": round(row["Compared to other Hopkins courses at this level, the workload for this course is:_mean"], 2),
                    "summary": trend_summary,
                })

    all_courses = sorted(df["course_number"].dropna().unique().tolist())
    all_instructors = sorted(df["instructor"].dropna().unique().tolist())

    def extract_level(code):
        match = re.match(r".*?(\d{3})$", code)
        if match:
            return match.group(1)[0] + "00"
        return None

    levels = sorted({extract_level(code) for code in all_courses if extract_level(code)})

    return render_template(
        "rec.html",
        dept_codes=DEPT_CODES,
        results=results,
        filter_type=filter_type,
        courses=all_courses,
        instructors=all_instructors,
        levels=levels,
    )
