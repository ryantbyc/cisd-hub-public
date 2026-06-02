#!/bin/bash
# CISD Hub — Synology Task Scheduler script
#
# In DSM: Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script
#   Task name:   CISD Hub Aggregator
#   User:        root
#   Schedule:    Daily at 20:00 (runs 3h after finance pipeline at 17:00)
#   Task Settings → paste this entire script
#
# Manual test run (as root over SSH):
#   bash /volume1/docker/cisd-hub/scripts/synology_task.sh

SCRIPT_DIR="/volume1/document/CISD-Hub-Public/scripts"
LOG_DIR="/volume1/docker/cisd-hub/logs"
LOG_FILE="$LOG_DIR/hub_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "====== CISD Hub Aggregator starting ======"

python3 "$SCRIPT_DIR/aggregate.py" --push >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    log "ERROR: aggregator exited with code $EXIT_CODE"
else
    log "Aggregator complete."
fi

# Rotate logs — keep last 30 days
find "$LOG_DIR" -name "hub_*.log" -mtime +30 -delete 2>/dev/null

log "====== Done ======"
exit $EXIT_CODE
