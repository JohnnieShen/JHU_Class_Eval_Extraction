#!/usr/bin/env python3
"""
Test paging on https://asen-jhu.evaluationkit.com:
  - Fetch page 1, list all <a class="sr-pdf"> links and their attrs
  - Detect and “click” the Show More button (#publicMore)
  - Repeat until no more button is found
"""
import http.cookiejar as cj
import requests
import textwrap
import time
from bs4 import BeautifulSoup

COOKIE_FILE = "cookies.txt"
BASE        = "https://asen-jhu.evaluationkit.com"
URL         = f"{BASE}/Report/Public/Results"
UA          = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

COURSE = "EN.601."

sess = requests.Session()
sess.headers.update(UA)
jar = cj.MozillaCookieJar()
jar.load(COOKIE_FILE, ignore_discard=True, ignore_expires=True)
for c in jar:
    sess.cookies.set_cookie(c)

def fetch_and_report(page: int) -> bool:
    params = {
        "Course": COURSE,
        "Instructor": "",
        "TermId": "",
        "Year": "",
        "AreaId": "",
        "QuestionKey": "",
        "Search": "true",
        "page": page
    }
    r = sess.get(URL, params=params, timeout=30)
    html = r.text

    print(f"\n--- PAGE {page} ({len(html)} bytes) ---")
    print("First 300 chars of HTML:")
    print(textwrap.shorten(html, width=300, placeholder=" …"), "\n")

    soup = BeautifulSoup(html, "html.parser")
    links = soup.select("a.sr-pdf")
    print(f"Found {len(links)} <a class='sr-pdf'> links")
    for i, a in enumerate(links, start=1):
        print(f"  link #{i}: text={a.get_text(strip=True)!r}")
        for k, v in a.attrs.items():
            print(f"     {k:<12}= {v}")
    print()

    btn = soup.select_one("a#publicMore")
    if btn:
        print(">> Show More button found! Attributes:")
        for k, v in btn.attrs.items():
            print(f"     {k:<12}= {v}")
        return True
    else:
        print(">> No Show More button on this page.")
        return False

def main():
    page = 1
    while True:
        has_more = fetch_and_report(page)
        if not has_more:
            break
        page += 1
        time.sleep(0.5)

if __name__ == "__main__":
    main()
