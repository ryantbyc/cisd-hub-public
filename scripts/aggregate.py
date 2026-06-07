#!/usr/bin/env python3
"""
CISD Hub aggregator.

Pulls the latest published data from each watchdog site and writes a single
docs/data/summary.json that the hub SPA renders. Deterministic Python only —
no LLM, no derived prose. Every number traces to a primary site's JSON.

Two source modes:
  --local <dir>   read sibling repo docs folders under <dir>
                  (cisd-bmm-public, cisd-finance-public, cisd-policy-public,
                   cisd-books-public). Used for local build/testing.
  (default)       fetch the live published JSON over HTTPS. Used in production
                  on the Synology task. GitHub Pages serves these with CORS *.

Run on the Synology schedule a few hours AFTER the finance pipeline so finance
data is fresh. Then commit docs/data/summary.json.
Two push modes:
  (default)   write docs/data/summary.json locally only.
  --push      also upload to GitHub via Contents API (no git binary needed).
              Reads GITHUB_TOKEN from env or /volume1/docker/cisd-hub/.env.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")

# ---- source configuration -------------------------------------------------
# Live domains. NOTE: meetings currently lives at cisd.boardmonitor.app; after
# the hub takes that domain it moves to meetings.boardmonitor.app. Override with
# CISD_MEETINGS_BASE while migration is pending.
LIVE = {
    "meetings":    os.environ.get("CISD_MEETINGS_BASE", "https://cisd-meetings.boardmonitor.app"),
    "finance":     "https://cisd-finance.boardmonitor.app",
    "policy":      "https://cisd-policy.boardmonitor.app",
    "books":       "https://cisd-books.boardmonitor.app",
    "performance": "https://cisd-performance.boardmonitor.app",
}
LOCAL_DIRS = {
    "meetings":    "cisd-bmm-public",
    "finance":     "cisd-finance-public",
    "policy":      "cisd-policy-public",
    "books":       "cisd-books-public",
    "performance": "cisd-performance-public",
}

NOW = datetime.now(timezone.utc)
ONE_YEAR_AGO = NOW - timedelta(days=365)


class Source:
    """Resolves a relative data path to either a local file or a live URL."""

    def __init__(self, local_base: Path | None):
        self.local_base = local_base

    def get(self, site: str, rel: str):
        if self.local_base is not None:
            p = self.local_base / LOCAL_DIRS[site] / "docs" / rel
            with open(p, "r", encoding="utf-8") as fh:
                return json.load(fh)
        url = f"{LIVE[site]}/{rel}"
        req = Request(url, headers={"User-Agent": "cisd-hub-aggregator/1.0"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


# ---- helpers --------------------------------------------------------------
def parse_date(s: str | None) -> datetime | None:
    """Parse YYYY-MM-DD, YYYY-MM, or ISO timestamps. Returns tz-aware UTC."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_meeting_time(time_str: str | None) -> tuple[int, int] | None:
    """'5:00 p.m.' / '6:00 PM' / '8:30 a.m.' -> (hour24, minute), else None."""
    if not time_str:
        return None
    m = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.?\s*m\.?", time_str.strip(), re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return h, mi


def ics_escape(s: str) -> str:
    """Escape text per RFC 5545 (backslash, comma, semicolon, newline)."""
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def build_next_meeting_ics(next_detail: dict | None) -> str | None:
    """
    Build a static .ics for the next board meeting — deterministic, no LLM.
    Requires next_detail['start_iso'] (an aware Central-time ISO datetime,
    populated in build_meetings from the authoritative scheduled.json).
    Returns None when we don't have a confident start time to anchor the event.
    """
    if not next_detail or not next_detail.get("start_iso"):
        return None
    try:
        start = datetime.fromisoformat(next_detail["start_iso"])
    except ValueError:
        return None
    end = start + timedelta(hours=2)  # typical board meeting block

    def fmt_utc(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    location = next_detail.get("location") or "Conroe ISD Administration Building, Conroe, TX"
    summary = f"CISD Board Meeting — {next_detail.get('type_display') or 'Meeting'}"
    description = ("Conroe ISD Board of Trustees meeting. "
                   "Live details and agenda: https://cisd-meetings.boardmonitor.app — "
                   "this is an independent constituent resource, not an official CISD calendar.")
    uid = f"{start.date().isoformat()}-{(next_detail.get('id') or 'scheduled-meeting')}@boardmonitor.app"

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CISD Board Monitor//Hub//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{NOW.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{fmt_utc(start)}",
        f"DTEND:{fmt_utc(end)}",
        f"SUMMARY:{ics_escape(summary)}",
        f"LOCATION:{ics_escape(location)}",
        f"DESCRIPTION:{ics_escape(description)}",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        "DESCRIPTION:CISD Board Meeting starts in 2 hours",
        "TRIGGER:-PT2H",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(lines) + "\r\n"


def md_section_bullets(md: str, heading: str, limit: int = 8) -> list[str]:
    """Pull '- ' bullets that follow a '## <heading>' until the next divider."""
    out: list[str] = []
    if not md:
        return out
    lines = md.splitlines()
    capture = False
    for ln in lines:
        st = ln.strip()
        if st.startswith("## ") and heading.lower() in st.lower():
            capture = True
            continue
        if capture:
            if st.startswith("## ") or st.startswith("---") or st.startswith("> "):
                if out:  # stop at the first divider after we've collected something
                    break
                continue
            if st.startswith("- "):
                out.append(st[2:].strip())
                if len(out) >= limit:
                    break
    return out


# ---- per-site builders ----------------------------------------------------
def build_meetings(src: Source) -> dict:
    idx = src.get("meetings", "data/index.json")
    meetings = idx.get("meetings", [])
    # newest-first in source, but sort defensively
    meetings = sorted(meetings, key=lambda m: m.get("meeting_date", ""), reverse=True)
    today = NOW.date().isoformat()

    upcoming = [m for m in meetings if m.get("meeting_date", "") >= today and not m.get("has_notes")]
    next_m = min(upcoming, key=lambda m: m["meeting_date"]) if upcoming else None
    completed = [m for m in meetings if m.get("has_notes")]
    last_m = completed[0] if completed else None

    # Authoritative schedule (clean ISO date + time + location) — used to anchor
    # a precise calendar event for the next meeting (for the .ics "Add to Calendar").
    schedule_by_date: dict[str, dict] = {}
    try:
        sched_idx = src.get("meetings", "data/scheduled.json")
        for s in sched_idx.get("meetings", []):
            if s.get("date"):
                schedule_by_date[s["date"]] = s
    except Exception:
        pass

    def schedule_start(date_iso: str | None) -> tuple[datetime | None, str | None]:
        """Combine YYYY-MM-DD + scheduled time -> aware Central-time datetime, plus location."""
        if not date_iso:
            return None, None
        s = schedule_by_date.get(date_iso)
        if not s:
            return None, None
        location = s.get("location") or None
        hm = parse_meeting_time(s.get("time"))
        if not hm:
            return None, location
        h, mi = hm
        try:
            y, mo, da = (int(x) for x in date_iso.split("-"))
            return datetime(y, mo, da, h, mi, tzinfo=CENTRAL), location
        except Exception:
            return None, location

    def detail(m, kind):
        if not m:
            return None
        doc = src.get("meetings", f"data/{m['id']}.json")
        if kind == "next":
            raw = doc.get("highlights") or ""
            bullets = [b[2:].strip() if b.strip().startswith("- ") else b.strip()
                       for b in raw.split("\n") if b.strip()]
        else:
            bullets = md_section_bullets(doc.get("meeting_notes_md", ""), "Meeting Highlights")
        d = {
            "id": m["id"],
            "date_display": m.get("date_display"),
            "type_display": m.get("type_display"),
            "item_count": m.get("item_count"),
            "highlights": bullets,
            "url": f"https://cisd-meetings.boardmonitor.app/meeting.html?id={m['id']}",
        }
        if kind == "next":
            start, location = schedule_start(m.get("meeting_date"))
            if start:
                d["start_iso"] = start.isoformat()
            if location:
                d["location"] = location
        return d

    next_detail = detail(next_m, "next")

    # If no agenda-bearing next meeting exists, fall back to scheduled.json for a stub.
    if next_detail is None:
        try:
            sched = src.get("meetings", "data/scheduled.json")
            future = [s for s in sched.get("meetings", []) if s.get("date", "") > today]
            if future:
                ns = min(future, key=lambda s: s["date"])
                d = datetime.strptime(ns["date"], "%Y-%m-%d")
                date_str = f"{d.strftime('%B')} {d.day}, {d.year}"
                extras = [p for p in [ns.get("time", ""), ns.get("location", "")] if p]
                if extras:
                    date_str += " - " + ", ".join(extras)
                t = ns.get("type", "regular")
                next_detail = {
                    "id": None,
                    "date_display": date_str,
                    "type_display": "Regular Meeting" if t == "regular" else "Special Meeting",
                    "item_count": None,
                    "highlights": [],
                    "url": None,
                    "scheduled_only": True,
                }
                start, location = schedule_start(ns["date"])
                if start:
                    next_detail["start_iso"] = start.isoformat()
                if location:
                    next_detail["location"] = location
        except Exception:
            pass

    return {
        "next": next_detail,
        "last": detail(last_m, "last"),
        "url": "https://cisd-meetings.boardmonitor.app",
    }


def fy_label(fy: str) -> str:
    """'2025-2026' or '2025-26' -> 'FY25-26'."""
    parts = fy.replace("FY", "").split("-")
    if len(parts) == 2:
        return f"FY{parts[0][-2:]}-{parts[1][-2:]}"
    return fy


def build_finance(src: Source) -> dict:
    meta = src.get("finance", "data/meta.json")

    # Annual budget — latest fiscal year.
    budget_val, budget_fy = None, None
    try:
        bt = src.get("finance", "data/budget_totals.json")
        if bt:
            budget_fy = max(bt.keys())
            budget_val = bt[budget_fy]
    except Exception:
        pass

    # Staff turnover — latest fiscal year's departures (rate unavailable upstream).
    departures, turn_sub = None, None
    try:
        turn = src.get("finance", "data/turnover.json")
        fys = turn.get("fiscal_years", [])
        if fys:
            latest = fys[-1]
            row = turn.get("summary", {}).get(latest, {})
            departures = row.get("departures")
            net = row.get("net")
            # latest FY is the in-progress year → year-to-date
            bits = [f"{fy_label(latest)} YTD"]
            if net is not None:
                bits.append(f"net {net:+d}")
            turn_sub = " · ".join(bits)
    except Exception:
        pass

    try:
        wd = src.get("finance", "data/watchdog.json")
        flags_total = len(wd)
        flags_high = sum(1 for f in wd if f.get("severity") == "high")
    except Exception:
        flags_total, flags_high = None, None

    metrics_out = [
        {"label": "Spend Tracked (6 yr)", "value": meta.get("total_spend"), "fmt": "usd_compact"},
        {"label": "Annual Budget", "value": budget_val, "fmt": "usd_compact",
         "sub": (fy_label(budget_fy) if budget_fy else None)},
        {"label": "Watchdog Flags", "value": flags_total, "fmt": "int",
         "sub": (f"{flags_high} high severity" if flags_high is not None else None)},
        {"label": "Staff Departures", "value": departures, "fmt": "int", "sub": turn_sub},
    ]
    return {
        "metrics": metrics_out,
        "data_updated": meta.get("last_updated"),
        "url": "https://cisd-finance.boardmonitor.app",
    }


def build_policy(src: Source) -> dict:
    idx = src.get("policy", "data/index.json")
    policies = idx.get("policies", [])
    tracked = sum(1 for p in policies if p.get("timeline_count"))
    adopted_12mo, latest_date, latest_code = 0, None, None
    total_revisions = 0
    for p in policies:
        total_revisions += int(p.get("timeline_count") or 0)
        d = parse_date(p.get("last_action_date"))
        if d:
            if d >= ONE_YEAR_AGO and (p.get("last_action_result") or "").lower() == "adopted":
                adopted_12mo += 1
            if latest_date is None or d > latest_date:
                latest_date, latest_code = d, p.get("code")

    metrics_out = [
        {"label": "Policy Changes (12 mo)", "value": adopted_12mo, "fmt": "int"},
        {"label": "Policies Tracked", "value": tracked, "fmt": "int"},
        {"label": "Revisions Logged", "value": total_revisions, "fmt": "int"},
        {"label": "Latest Change", "value": latest_code, "fmt": "text",
         "sub": (latest_date.strftime("%b %Y") if latest_date else None)},
    ]
    return {"metrics": metrics_out, "url": "https://cisd-policy.boardmonitor.app"}


def build_books(src: Source) -> dict:
    data = src.get("books", "data/books.json")
    counts = data.get("action_counts", {})
    removed_12mo = 0
    reconsiderations = 0
    for b in data.get("books", []):
        for a in b.get("actions", []):
            d = parse_date(a.get("date"))
            outcome = (a.get("outcome") or "").lower()
            if outcome == "removed" and d and d >= ONE_YEAR_AGO:
                removed_12mo += 1
            blob = " ".join(str(a.get(k) or "") for k in ("type", "process", "reason_label")).lower()
            if "reconsideration" in blob:
                reconsiderations += 1

    metrics_out = [
        {"label": "Books Removed", "value": counts.get("removed"), "fmt": "int",
         "sub": "all-time"},
        {"label": "Titles Tracked", "value": data.get("total_books"), "fmt": "int"},
        {"label": "Reconsiderations", "value": reconsiderations, "fmt": "int"},
        {"label": "Retained", "value": counts.get("retained"), "fmt": "int"},
    ]
    return {
        "metrics": metrics_out,
        "removed_12mo": removed_12mo,
        "pending": counts.get("pending", 0),
        "url": "https://cisd-books.boardmonitor.app",
    }


def build_performance(src: Source) -> dict:
    """Extract headline district metrics from the performance site's outcomes.json."""
    data = src.get("performance", "data/outcomes.json")
    tm = data.get("tea_metrics", {}).get("district", {})

    # Find years that have accountability data, sorted newest-first
    years_with_data = sorted(
        [(yr, yd) for yr, yd in tm.items() if yd.get("accountability")],
        key=lambda x: x[0], reverse=True,
    )
    if not years_with_data:
        return {"grade": None, "metrics": [], "url": "https://cisd-performance.boardmonitor.app"}

    curr_yr, curr = years_with_data[0]
    prev_yr, prev = years_with_data[1] if len(years_with_data) > 1 else (None, {})

    def find(metrics_list: list, prefix: str) -> float | None:
        for m in metrics_list:
            if m.get("title", "").startswith(prefix):
                return m.get("all")
        return None

    def delta(curr_val, prev_val) -> float | None:
        if curr_val is None or prev_val is None:
            return None
        return round(curr_val - prev_val, 1)

    c_ap = curr.get("academic_performance", [])
    c_gp = curr.get("graduation_postsec", [])
    p_ap = prev.get("academic_performance", []) if prev else []
    p_gp = prev.get("graduation_postsec", []) if prev else []

    metrics = [
        {
            "label": "STAAR Reading", "sub": "Meets Grade Level+", "fmt": "pct",
            "value": find(c_ap, "STAAR Reading"),
            "trend": delta(find(c_ap, "STAAR Reading"), find(p_ap, "STAAR Reading")),
        },
        {
            "label": "STAAR Math", "sub": "Meets Grade Level+", "fmt": "pct",
            "value": find(c_ap, "STAAR Math"),
            "trend": delta(find(c_ap, "STAAR Math"), find(p_ap, "STAAR Math")),
        },
        {
            "label": "Graduation Rate", "sub": "4-Year", "fmt": "pct",
            "value": find(c_gp, "4-Year Graduation"),
            "trend": delta(find(c_gp, "4-Year Graduation"), find(p_gp, "4-Year Graduation")),
        },
        {
            "label": "CCMR", "sub": "College, Career & Military Ready", "fmt": "pct",
            "value": find(c_gp, "College, Career"),
            "trend": delta(find(c_gp, "College, Career"), find(p_gp, "College, Career")),
        },
        {
            "label": "Dropout Rate", "sub": "Grades 9–12", "fmt": "pct",
            "lower_is_better": True,
            "value": find(c_gp, "Annual Dropout"),
            "trend": delta(find(c_gp, "Annual Dropout"), find(p_gp, "Annual Dropout")),
        },
    ]

    return {
        "school_year": curr_yr,
        "grade": curr.get("accountability", {}).get("grade"),
        "metrics": metrics,
        "url": "https://cisd-performance.boardmonitor.app",
    }


GITHUB_OWNER = "ryantbyc"
GITHUB_REPO  = "cisd-hub-public"
GITHUB_PATH  = "docs/data/summary.json"
NAS_ENV_FILE = "/volume1/docker/cisd-hub/.env"


def load_token() -> str:
    """Read GITHUB_TOKEN from environment or NAS .env file."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token and Path(NAS_ENV_FILE).exists():
        for line in Path(NAS_ENV_FILE).read_text().splitlines():
            line = line.strip()
            if line.startswith("GITHUB_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not token:
        raise RuntimeError(
            f"GITHUB_TOKEN not found in environment or {NAS_ENV_FILE}"
        )
    return token


def github_api(method: str, path: str, token: str, body: dict | None = None):
    """Minimal GitHub REST API call using stdlib only."""
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cisd-hub-aggregator/1.0",
        **({"Content-Type": "application/json"} if data else {}),
    })
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def push_file(repo_path: str, content: str, message: str, token: str) -> None:
    """Upload a text file to GitHub via the Contents API (no git binary needed)."""
    api_path = f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{repo_path}"
    # Get current SHA so GitHub accepts the update.
    try:
        current = github_api("GET", api_path, token)
        sha = current.get("sha")
    except HTTPError as e:
        if e.code == 404:
            sha = None  # file doesn't exist yet — first push
        else:
            raise
    body = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": "main",
    }
    if sha:
        body["sha"] = sha
    github_api("PUT", api_path, token, body)
    print(f"pushed {repo_path} to GitHub via API")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", help="base dir holding sibling repo clones (build/test mode)")
    ap.add_argument("--push", action="store_true", help="upload to GitHub via Contents API after writing locally")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "docs" / "data" / "summary.json"))
    args = ap.parse_args()

    src = Source(Path(args.local) if args.local else None)

    summary = {
        "generated_at": NOW.isoformat(),
        "source_mode": "local" if args.local else "live",
        "sites": {},
        "errors": {},
    }
    for name, fn in (("meetings", build_meetings), ("performance", build_performance),
                     ("finance", build_finance), ("policy", build_policy),
                     ("books", build_books)):
        try:
            summary["sites"][name] = fn(src)
        except Exception as e:  # one site down must not blank the whole hub
            summary["errors"][name] = f"{type(e).__name__}: {e}"
            print(f"[warn] {name}: {e}", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Pre-generated "Add to Calendar" .ics for the next board meeting — deterministic,
    # built straight from scheduled.json's date/time/location (no LLM, no derived prose).
    ics_content = None
    meetings_site = summary["sites"].get("meetings")
    if meetings_site and meetings_site.get("next"):
        ics_content = build_next_meeting_ics(meetings_site["next"])
        if ics_content:
            ics_out = out.parent / "next-meeting.ics"
            with open(ics_out, "w", encoding="utf-8", newline="") as fh:
                fh.write(ics_content)
            meetings_site["ics_url"] = "data/next-meeting.ics"
            print(f"wrote {ics_out}")

    content = json.dumps(summary, indent=2, ensure_ascii=False)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"wrote {out} ({len(summary['sites'])} sites, {len(summary['errors'])} errors)")

    if args.push:
        token = load_token()
        push_file(GITHUB_PATH, content,
                  f"data: refresh hub summary ({NOW.strftime('%Y-%m-%dT%H:%MZ')})", token)
        if ics_content:
            push_file("docs/data/next-meeting.ics", ics_content,
                      f"data: refresh next-meeting.ics ({NOW.strftime('%Y-%m-%dT%H:%MZ')})", token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
