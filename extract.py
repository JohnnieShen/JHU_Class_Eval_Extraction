import fitz  # PyMuPDF
import re
import pandas as pd
from pathlib import Path
import time

def extract_metadata(text):
    instructor_match = re.search(r"\n([^\n]+?)\s*Instructor", text)
    course_match = re.search(r"Course:\s*([A-Z0-9\.]+)\s*:\s*(.+?)\n", text)
    term_match = re.search(r"(\d{4})\s+(Spring|Fall|Summer|Intersession)", text)

    if course_match:
        course_number = course_match.group(1).strip()
        course_name = course_match.group(2).strip()
        parts = course_number.split(".")
        if len(parts) >= 3:
            course_number = ".".join(parts[:3])
    else:
        course_number = course_name = None

    return {
        "course_number": course_number,
        "course_name": course_name,
        "instructor": instructor_match.group(1).strip() if instructor_match else None,
        "year": term_match.group(1) if term_match else None,
        "term": term_match.group(2) if term_match else None,
    }

def extract_question_data(block):
    lines = block.strip().splitlines()
    question_title = lines[0]

    responses = re.findall(r'\((\d)\)\s+(\d+)\s+\d{1,3}\.\d{2}%', block)

    respondent_match = re.search(r"(\d+)/\d+\s+\(\d{1,3}%\)", block)
    num_respondents = int(respondent_match.group(1)) if respondent_match else 0

    return {
        "question_title": question_title,
        "responses": [(int(weight), int(count)) for weight, count in responses],
        "respondents": num_respondents
    }

def extract_respondents_from_filename(fname):
    m = re.search(r'(\d+)[_\s]+of[_\s]+\d+[_\s]+responded', fname, re.IGNORECASE)
    return int(m.group(1)) if m else 0

def process_pdf(file_path):
    doc = fitz.open(file_path)
    all_text = "".join(page.get_text() for page in doc)

    metadata = extract_metadata(all_text)
    question_blocks = re.split(r"\n\d+\s*-\s*", all_text)[1:]

    questions_dict = {}
    respondent_counts = []

    for block in question_blocks:
        q = extract_question_data(block)
        if not q["responses"]:
            continue

        if q["question_title"] not in questions_dict:
            questions_dict[q["question_title"]] = q["responses"]

    row = {
        "file": Path(file_path).name,
        "course_number": metadata["course_number"],
        "course_name": metadata["course_name"],
        "instructor": metadata["instructor"],
        "year": metadata["year"],
        "term": metadata["term"],
        "num_respondents": max(respondent_counts) if respondent_counts else 0
    }
    row.update(questions_dict)
    n = extract_respondents_from_filename(file_path.name)
    row["num_respondents"] = n if n is not None else 0
    return row

def is_row_complete(row):
    meta = ["course_number","course_name","instructor","year","term"]
    for m in meta:
        if not row.get(m):
            return False

    for key, val in row.items():
        if key in meta + ["file","num_respondents"]:
            continue

        if not isinstance(val, list):
            return False

    return True

def append_row_to_csv(row, csv_path="all_course_stats.csv"):
    df = pd.DataFrame([row])
    write_header = not Path(csv_path).exists()
    df.to_csv(csv_path, mode="a", index=False, header=write_header)

def watch_and_process(folder_path="pdfs", poll_interval=5):
    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    processed = set()

    print(f"Watching `{folder}` for new PDFs")
    try:
        while True:
            for pdf_file in folder.glob("*.pdf"):
                if pdf_file.name in processed:
                    continue

                print(f"New file: {pdf_file.name}")
                try:
                    row = process_pdf(pdf_file)
                    append_row_to_csv(row)
                    pdf_file.unlink()
                    processed.add(pdf_file.name)
                    print(f"Processed & deleted `{pdf_file.name}`")
                except Exception as e:
                    print(f"Error processing `{pdf_file.name}`: {e}")

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nStopped watching.")

if __name__ == "__main__":
    watch_and_process("pdfs", poll_interval=5)