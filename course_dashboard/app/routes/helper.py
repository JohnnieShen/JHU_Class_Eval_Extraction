import pandas as pd
import ast


def summarize_instructor(name, instructor_df):
    if instructor_df.empty:
        return (name, "No data", "-", "-", "-")

    scores = instructor_df['teaching_avg'].dropna().tolist()
    dates = instructor_df['term_date'].dropna().tolist()
    labels = instructor_df['term_label'].dropna().tolist()

    if not scores:
        return (name, "No rating data", "-", "-", "-")

    avg = np.mean(scores)
    trend = summarize_trend(scores, dates)
    semesters = len(scores)
    most_recent = labels[-1] if labels else "Unknown"

    return (name, f"{avg:.2f}", trend, semesters, most_recent)

def compute_weighted_avg(response_str):
    try:
        ratings = ast.literal_eval(response_str)
        total_score = sum(score * count for score, count in ratings if score != 0)
        total_responses = sum(count for score, count in ratings if score != 0)
        return total_score / total_responses if total_responses > 0 else None
    except:
        return None
    
def parse_term(term, year):
    if pd.isna(term) or pd.isna(year):
        return pd.NaT, "Unknown"
    term = term.strip()
    month_map = {"Spring": 1, "Summer": 6, "Fall": 9}
    month = month_map.get(term, 1)
    try:
        date = pd.to_datetime(f"{int(year)}-{month}-01")
        return date, f"{term} {year}"
    except:
        return pd.NaT, "Unknown"


def summarize_trend(scores, dates):
    valid = [(s, d) for s, d in zip(scores, dates) if pd.notna(s) and pd.notna(d)]
    if len(valid) < 2:
        return "Not enough data"
    valid.sort(key=lambda x: x[1])
    start, end = valid[0][0], valid[-1][0]
    delta = end - start
    if abs(delta) < 0.1:
        return "Stayed the same"
    return "Improved" if delta > 0 else "Declined"



def load_and_prepare_data(file_path):
    df = pd.read_csv(file_path)

    df[['school', 'dept', 'course', 'section', 'term_year']] = df['course_number'].str.extract(
        r'([A-Z]{2})\.(\d{3})\.(\d{3})\.(\d{2})\.([A-Z]{2}\d{2})'
    )

    parsed_terms = df['term_year'].apply(parse_term)
    df['term_date'] = parsed_terms.apply(lambda x: x[0])
    df['term_label'] = parsed_terms.apply(lambda x: x[1])

    return df

DEPT_CODES = {
    "001": "AS First Year Seminars",
    "004": "AS University Writing Program",
    "010": "History of Art",
    "020": "Biology",
    "030": "Chemistry",
    "040": "Classics",
    "050": "Cognitive Science",
    "060": "English",
    "061": "Film and Media Studies",
    "070": "Anthropology",
    "080": "Neuroscience",
    "100": "History",
    "110": "Mathematics",
    "130": "Near Eastern Studies",
    "131": "Near Eastern Studies",
    "132": "Near Eastern Studies",
    "133": "Near Eastern Studies",
    "134": "Near Eastern Studies",
    "136": "Archaeology",
    "140": "History of Science, Medicine, and Technology",
    "145": "Medicine, Science, and the Humanities",
    "150": "Philosophy",
    "171": "Physics and Astronomy",
    "172": "Physics and Astronomy",
    "173": "Physics and Astronomy",
    "180": "Economics",
    "190": "Political Science",
    "191": "Political Science",
    "192": "International Studies",
    "194": "Islamic Studies",
    "196": "Agora Institute",
    "197": "Center for Economy and Society",
    "200": "Psychological and Brain Sciences",
    "210": "Modern Languages and Literature",
    "211": "Modern Languages and Literature",
    "212": "Modern Languages and Literature",
    "213": "Modern Languages and Literature",
    "214": "Modern Languages and Literature",
    "215": "Modern Languages and Literature",
    "216": "Modern Languages and Literature",
    "217": "Modern Languages and Literature",
    "220": "Writing Seminars",
    "225": "Theater Arts and Studies",
    "230": "Sociology",
    "250": "Biophysics",
    "270": "Earth and Planetary Science",
    "271": "Earth and Planetary Science",
    "280": "Public Health Studies",
    "290": "Behavioral Biology",
    "300": "Comparative Thought and Literature",
    "310": "East Asian Studies",
    "360": "Interdepartmental",
    "361": "Latin American, Caribbean, and Latinx Studies",
    "362": "Africana Studies",
    "363": "Women, Gender, and Sexuality",
    "370": "English as a Second Language",
    "371": "Art",
    "373": "Chinese",
    "374": "Military Science",
    "375": "Arabic",
    "376": "Music",
    "377": "Russian",
    "378": "Japanese",
    "380": "Korean",
    "381": "Hindi",
    "384": "Hebrew",
    "389": "Program in Museums and Society",
    "500": "General Engineering",
    "501": "EN First Year Seminars",
    "510": "Materials Science and Engineering",
    "520": "Electrical and Computer Engineering",
    "530": "Mechanical Engineering",
    "540": "Chemical and Biomolecular Engineering",
    "553": "Applied Mathematics and Statistics",
    "560": "Civil and Systems Engineering",
    "570": "Environmental Health & Engineering",
    "580": "Biomedical Engineering",
    "601": "Computer Science",
    "620": "Robotics",
    "650": "Information Security Institute",
    "660": "Entrepreneurship & Management",
    "661": "Professional Communication",
    "662": "Engineering Management",
    "663": "Center for Leadership Education",
    "670": "Nanobiotechnology",
    "700": "Doctor of Engineering"
}


rating_columns = [
        "The instructor's teaching effectiveness is:",
        'The intellectual challenge of this course is:',
        'Feedback on my work for this course is useful:',
        'Compared to other Hopkins courses at this level, the workload for this course is:'
    ]