#!/bin/sh
# CISD Hub — daily aggregation task for Synology Task Scheduler.
# Schedule a few hours AFTER the finance pipeline's 17:00 CT run so finance
# data is fresh (e.g. 20:00 CT). Regenerates docs/data/summary.json and pushes.
set -eu

REPO_DIR="${CISD_HUB_REPO:-/volume1/docker/cisd-hub/repo}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# Until BMM migrates off cisd.boardmonitor.app, read meetings from the current
# host. After migration, delete this line (default is meetings.boardmonitor.app).
export CISD_MEETINGS_BASE="${CISD_MEETINGS_BASE:-https://cisd.boardmonitor.app}"

cd "$REPO_DIR"
git pull --ff-only origin main

"$PYTHON_BIN" scripts/aggregate.py

if ! git diff --quiet -- docs/data/summary.json; then
  git add docs/data/summary.json
  git commit -m "data: refresh hub summary ($(date -u +%Y-%m-%dT%H:%MZ))"
  git push origin main
  echo "summary.json updated and pushed"
else
  echo "no change in summary.json"
fi
