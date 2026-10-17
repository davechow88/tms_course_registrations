"""Daily snapshot of the public KnowledgeTree TMS course schedule.

Reads https://tms.ktree.com.sg/CourseSchedule/Index (public, no login),
records the places remaining for every listed session, and writes:

  data/snapshots/<YYYY-MM-DD>.json   one file per day (Singapore date)
  data/latest.json                   copy of the most recent snapshot

Read-only: it only loads the public schedule page, never logs in or submits anything.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://tms.ktree.com.sg/CourseSchedule/Index"
PAGE_SIZE = 500
SGT = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 ktree-slot-tracker/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-SG,en;q=0.9",
}

# Course titles that do not end in a "(CODE)" suffix get a fixed short code.
SPECIAL_CODES = {
    "Quality Assurance and Professional Practice for Adult Educators": "QAPP",
}


def course_code(title: str) -> str:
    if title in SPECIAL_CODES:
        return SPECIAL_CODES[title]
    m = re.search(r"\(([^()]+)\)\s*$", title)
    if m:
        return m.group(1).strip()
    words = re.findall(r"[A-Za-z]+", title)
    return "".join(w[0] for w in words if w[0].isupper()) or title


def iso_date(dmy: str) -> str:
    d, m, y = dmy.strip().split("/")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def fetch_html() -> str:
    resp = requests.get(URL, params={"pageSize": PAGE_SIZE}, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.text


def parse(html: str) -> tuple[int | None, list[list[str]]]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    m = re.search(r"Showing\s+\d+\s+to\s+\d+\s+of\s+(\d+)\s+records", text)
    expected = int(m.group(1)) if m else None
    rows: list[list[str]] = []
    for tr in soup.select("table tbody tr"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) >= 8:
            rows.append(cells)
    return expected, rows


def build(rows: list[list[str]], snapshot_at: str) -> list[dict]:
    out: list[dict] = []
    seen: dict[str, int] = {}
    for c in rows:
        title, level, timing, start, end, _tests, remarks, places = c[:8]
        code = course_code(title)
        s, e = iso_date(start), iso_date(end)
        key = f"{code}|{timing}|{s}|{e}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}|{seen[key]}"
        out.append(
            {
                "snapshot_at": snapshot_at,
                "snapshot_date": snapshot_at[:10],
                "session": key,
                "code": code,
                "course": title,
                "level": level,
                "timing": timing,
                "start": s,
                "end": e,
                "remarks": remarks,
                "places": int(re.sub(r"[^0-9-]", "", places) or 0),
            }
        )
    return out


def fail(msg: str) -> int:
    # "::error::" lines show up as annotations on the GitHub Actions run.
    print(f"::error::{msg}")
    print(msg, file=sys.stderr)
    return 1


def main() -> int:
    now = datetime.now(SGT).replace(second=0, microsecond=0)
    snapshot_at = now.isoformat()
    try:
        html = fetch_html()
    except requests.RequestException as exc:
        return fail(f"Could not load the schedule page: {type(exc).__name__}: {str(exc)[:300]}")
    expected, raw = parse(html)
    if not raw:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        tables = len(soup.find_all("table"))
        return fail(
            f"No schedule rows found (page title {title!r}, {len(html)} bytes, {tables} tables, "
            f"'Course Title' present: {'Course Title' in html}). The layout may have changed."
        )
    if expected is not None and expected != len(raw):
        return fail(f"Page says {expected} records but {len(raw)} rows were read.")
    rows = build(raw, snapshot_at)
    snap = {
        "snapshot_at": snapshot_at,
        "source": URL,
        "count": len(rows),
        "places_total": sum(r["places"] for r in rows),
        "fully_booked": sum(1 for r in rows if r["places"] == 0),
        "rows": rows,
    }
    (DATA / "snapshots").mkdir(parents=True, exist_ok=True)
    body = json.dumps(snap, ensure_ascii=False, indent=1)
    (DATA / "snapshots" / f"{snapshot_at[:10]}.json").write_text(body + "\n", encoding="utf-8")
    (DATA / "latest.json").write_text(body + "\n", encoding="utf-8")
    print(f"{snapshot_at}: {snap['count']} sessions, {snap['places_total']} places left, {snap['fully_booked']} fully booked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
