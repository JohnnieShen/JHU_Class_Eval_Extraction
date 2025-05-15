from __future__ import annotations
import argparse, os, re, sys, time, urllib.parse as up, http.cookiejar as cj
import requests, requests.exceptions as REx
from bs4 import BeautifulSoup
from tqdm import tqdm
from pathlib import Path

BASE   = "https://asen-jhu.evaluationkit.com"
HTML   = f"{BASE}/Report/Public/Results"          # page 1
API    = f"{BASE}/AppApi/Report/PublicReport"     # page 3,4,…
UA     = {"User-Agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
BAD    = "wwww.evaluationkit.com"                 # poisoned redirect
CHUNK  = 20                                       # rows per server chunk
COOKIE = "cookies.txt"

N_RETRY = 4               # total attempts = N_RETRY
BACKOFF = 1.0             # first wait in seconds (doubles each try)

def load_cookies(sess: requests.Session) -> None:
    if not os.path.exists(COOKIE):
        print("[warn] cookies.txt not found – export your Watermark cookies first")
        return
    jar = cj.MozillaCookieJar(); jar.load(COOKIE, ignore_discard=True, ignore_expires=True)
    for c in jar: sess.cookies.set_cookie(c)
    print(f"[dbg] loaded {len(jar)} cookies")

def safe_get(sess: requests.Session, url: str, **kw) -> requests.Response:
    r = sess.get(url, allow_redirects=False, **kw)
    if r.is_redirect and BAD in r.headers.get("Location", ""):
        r = sess.get(r.headers["Location"].replace(BAD, "www.evaluationkit.com"), **kw)
    r.raise_for_status(); return r

def safe_get_retry(sess: requests.Session, url: str, **kw) -> requests.Response:
    """safe_get with exponential‑back‑off retries on 5xx/429 or transport errors"""
    wait = BACKOFF
    exc: Exception | None = None
    for attempt in range(1, N_RETRY + 1):
        try:
            r = safe_get(sess, url, **kw)
            return r
        except (REx.HTTPError, REx.ConnectionError, REx.Timeout) as er:
            exc = er
            code = getattr(er.response, "status_code", None)
            if attempt == N_RETRY or (isinstance(er, REx.HTTPError) and code and 400 <= code < 500 and code != 429):
                break
            print(f"[retry {attempt}/{N_RETRY} after {wait:.1f}s] {url} – {er}")
            time.sleep(wait)
            wait *= 2
    assert exc is not None
    raise exc

def fetch_page(sess, prefix: str, page: int) -> tuple[str, bool]:
    params = dict(Course=prefix, Instructor="", TermId="", Year="",
                  AreaId="", QuestionKey="", Search="true", page=page)

    if page == 1:
        r   = safe_get_retry(sess, HTML, params=params, timeout=30)
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        more = bool(soup.select_one("#publicMore"))
        print(f"[dbg] GET Results page=1  → {len(html):,} bytes, more={more}")
        return html, more

    hdrs = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01"
    }
    r = safe_get_retry(sess, API, params=params, headers=hdrs, timeout=30)
    data = r.json()
    html = "".join(data.get("results", []))
    more = bool(data.get("hasMore", False))
    print(f"[dbg] GET PublicReport page={page} → {len(html):,} bytes, more={more}")
    return html, more

def extract_pdfs(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    out  = []
    for a in soup.select("a.sr-pdf"):
        url   = (f"{BASE}/Reports/SRPdf.aspx?"
                 f"{a['data-id0']},{a['data-id1']},{a['data-id2']},{a['data-id3']}")
        card  = a.find_parent(class_=re.compile(r"(panel|card)")) or a.parent
        title = card.get_text(" ", strip=True)
        fname = re.sub(r"[^\w\- ]", "_", title) + ".pdf"
        out.append((url, fname))
    return out

def save_pdf(sess: requests.Session, url: str, dst: str) -> None:
    if os.path.exists(dst): return
    r = safe_get_retry(sess, url, stream=False, timeout=30)
    if "text/html" in r.headers.get("Content-Type", ""):
        m = re.search(r"document\.location\.href\s*=\s*['\"](.+?)['\"]", r.text)
        if not m:
            print(f"[ERROR] couldn’t find redirect inside {url}")
            return
        r = safe_get_retry(sess, up.urljoin(r.url, m.group(1)), stream=True, timeout=60)

    if "application/pdf" not in r.headers.get("Content-Type", ""):
        print(f"[ERROR] expected PDF, got {r.headers.get('Content-Type')} from {r.url}")
        return

    with open(dst, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

def prefixes():
    for stem in ("AS.", "EN."):
        for n in range(1000):
            yield f"{stem}{n:03d}"

_PREFIX_RE = re.compile(r"^(AS|EN)(?:\.(\d{3}))?$")

def make_prefix_iter(user_prefix: str | None):
    if user_prefix is None:
        def _all():
            for stem in ("AS.", "EN."):
                for n in range(1000):
                    yield f"{stem}{n:03d}"
        return _all()

    m = _PREFIX_RE.fullmatch(user_prefix.strip().upper())
    if not m:
        sys.exit(f"[error] --prefix must be AS | EN | AS.xxx | EN.xxx  (got “{user_prefix}”)")

    stem, number = m.groups()
    if number is None:
        def _stem():
            for n in range(1000):
                yield f"{stem}.{n:03d}"
        return _stem()
    else:
        return iter([f"{stem}.{number}"])

def crawl(out_dir: str, delay: float, live: bool, prefix_filter: str | None):
    out_path = Path(out_dir.replace("\\", os.sep)).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    sess = requests.Session()
    sess.headers.update(UA)
    load_cookies(sess)

    seen: set[str] = set()
    for pref in tqdm(make_prefix_iter(prefix_filter), desc="Prefixes"):
        html, more = fetch_page(sess, pref, 1)
        rows = extract_pdfs(html)
        print(f"[dbg] {pref} page1: {len(rows)} links")

        new = 0
        for url, fname in rows:
            rid = url.split("?", 1)[1]
            if rid in seen:
                continue
            seen.add(rid)
            new += 1
            if live:
                print(f"Downloading → {fname}")
                save_pdf(sess, url, out_path / fname)
        print(f"[dbg] {pref}: +{new} new from page1")

        api_page = 3
        while more:
            html, more = fetch_page(sess, pref, api_page)
            rows = extract_pdfs(html)
            print(f"[dbg] {pref} page{api_page}: {len(rows)} links")
            if not rows:
                break

            new = 0
            for url, fname in rows:
                rid = url.split("?", 1)[1]
                if rid in seen:
                    continue
                seen.add(rid)
                new += 1
                if live:
                    print(f"Downloading → {fname}")
                    save_pdf(sess, url, out_path / fname)
            print(f"[dbg] {pref}: +{new} new so far")

            if len(rows) < CHUNK:
                break
            api_page += 1
            time.sleep(delay)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="actually download PDFs (omit for dry-run)")
    ap.add_argument("-d", "--delay", type=float, default=0.4,
                    help="seconds to sleep between HTTP requests")

    out_grp = ap.add_mutually_exclusive_group()
    out_grp.add_argument("-o", "--out", metavar="DIR", default="pdfs",
                         help="*relative* output folder (default: %(default)s)")
    out_grp.add_argument("--abs-out", metavar="DIR",
                         help="*absolute* output folder (mutually exclusive)")

    ap.add_argument("--prefix",
                    help="AS | EN | AS.xxx | EN.xxx  (restrict crawl)")
    args = ap.parse_args()

    out_dir = args.abs_out if args.abs_out else args.out
    crawl(out_dir, args.delay, args.live, args.prefix)
