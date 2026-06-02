#!/bin/bash
# CISD Hub — Synology Task Scheduler script
#
# In DSM: Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script
#   Task name:   CISD Hub Aggregator
#   User:        root
#   Schedule:    Daily at 20:00 (runs after finance pipeline at 17:00)
#   Task Settings → paste this entire script
#
# Manual test run (as root over SSH):
#   bash /volume1/docker/cisd-hub/scripts/synology_task.sh

REPO_DIR="/volume1/docker/cisd-hub/repo"
LOG_DIR="/volume1/docker/cisd-hub/logs"
LOG_FILE="$LOG_DIR/hub_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "====== CISD Hub Aggregator starting ======"

cd "$REPO_DIR" || { log "ERROR: Cannot cd to $REPO_DIR"; exit 1; }

log "Pulling latest code..."
git pull --ff-only origin main >> "$LOG_FILE" 2>&1 || {
    log "WARNING: git pull failed — continuing with current code"
}

log "Running aggregator (live mode)..."
python3 scripts/aggregate.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    log "ERROR: aggregator exited with code $EXIT_CODE"
    exit $EXIT_CODE
fi

if ! git diff --quiet -- docs/data/summary.json; then
    log "summary.json changed — committing and pushing..."
    git add docs/data/summary.json
    git commit -m "data: refresh hub summary ($(date -u +%Y-%m-%dT%H:%MZ))" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1
    log "Push complete."
else
    log "No change in summary.json — nothing to push."
fi

# Rotate logs — keep last 30 days
find "$LOG_DIR" -name "hub_*.log" -mtime +30 -delete 2>/dev/null

log "====== Done ======"
exit 0
