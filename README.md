# CISD Hub

Launchpad / home page for the CISD watchdog family. A single static SPA that
surfaces the latest update from each site:

- **Board Meetings** (`meetings.boardmonitor.app`) — next meeting + agenda highlights, last meeting + summary highlights (tap to expand)
- **Finance** (`cisd-finance.boardmonitor.app`) — 4 headline metrics
- **Policy** (`cisd-policy.boardmonitor.app`) — 4 change metrics
- **Library Books** (`cisd-books.boardmonitor.app`) — 4 removal/challenge metrics

Lives at **`cisd.boardmonitor.app`**. Static, GitHub Pages from `docs/`. No build step.

## How it works

`scripts/aggregate.py` pulls each site's published JSON and writes one
`docs/data/summary.json`. The SPA (`docs/app.js`) renders that file. Deterministic
Python only — every number traces to a primary site's data (Python-first, LLM-last).

### Regenerate locally (reads sibling repo clones)

```sh
python scripts/aggregate.py --local C:\Temp
# expects C:\Temp\cisd-{bmm,finance,policy,books}-public\docs\...
```

### Production (fetches live URLs)

```sh
python scripts/aggregate.py        # no --local → live mode
```

Runs on the Synology Task Scheduler a few hours **after** the finance pipeline
(so finance data is fresh). See `scripts/synology_task.sh`.

> **Domain migration note:** until BMM moves off `cisd.boardmonitor.app` to
> `meetings.boardmonitor.app`, point the aggregator at the current meetings host:
> `CISD_MEETINGS_BASE=https://cisd.boardmonitor.app python scripts/aggregate.py`

## Tech Stack

| Layer | What |
|---|---|
| **Frontend** | Vanilla HTML + CSS + JavaScript — no framework, no build step |
| **Hosting** | GitHub Pages (`docs/` folder → `cisd.boardmonitor.app`) |
| **Data** | `docs/data/summary.json` — fetched at runtime by `app.js` via `fetch()` |
| **Aggregator** | Python 3 stdlib only (`scripts/aggregate.py`) — pulls JSON from each sibling site, writes `summary.json` |
| **Scheduler** | Synology NAS Task Scheduler — runs the aggregator every few hours after the finance pipeline |
| **Push mechanism** | GitHub Contents API (no git binary on NAS) — `aggregate.py --push` uploads `summary.json` directly |
| **Alerts API** | `https://api.boardmonitor.app` — external endpoint for email alert sign-ups (meetings card) |
| **CSS** | Hand-rolled design tokens (no CSS framework), system font stack |

No npm, no bundler, no server-side rendering. The entire site is static files; the only "backend" is the Python aggregator running on a schedule.

## Design

`.interface-design/system.md` — "Sophistication & Trust" tokens (spacing, color,
type, components). `docs/styles.css` mirrors those tokens. Follow them when adding UI.

## Local preview

```sh
python -m http.server 8099 --directory docs
# open http://localhost:8099
```
