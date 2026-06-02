#!/bin/bash
# CISD Hub — One-time NAS setup script
# Run as root over SSH on the Synology:
#   bash /path/to/setup_nas.sh <github_token>
#
# The GitHub token needs: repo (read + write) on ryantbyc/cisd-hub-public.
# You can create one at: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained.

set -eu

GITHUB_TOKEN="${1:-}"
GITHUB_USER="ryantbyc"
REPO="cisd-hub-public"
REPO_DIR="/volume1/docker/cisd-hub/repo"
LOG_DIR="/volume1/docker/cisd-hub/logs"
SCRIPTS_DIR="/volume1/docker/cisd-hub/scripts"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Usage: bash setup_nas.sh <github_personal_access_token>"
    exit 1
fi

echo "==> Creating directories..."
mkdir -p "$REPO_DIR" "$LOG_DIR" "$SCRIPTS_DIR"

echo "==> Cloning repo..."
if [ -d "$REPO_DIR/.git" ]; then
    echo "    Already cloned — skipping."
else
    git clone "https://${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO}.git" "$REPO_DIR"
fi

echo "==> Configuring git identity..."
git -C "$REPO_DIR" config user.name "CISD Hub NAS"
git -C "$REPO_DIR" config user.email "bog.graph-3v@icloud.com"

echo "==> Storing token in remote URL (credential-free push)..."
git -C "$REPO_DIR" remote set-url origin \
    "https://${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO}.git"

echo "==> Copying task script to persistent location..."
cp "$REPO_DIR/scripts/synology_task.sh" "$SCRIPTS_DIR/synology_task.sh"
chmod +x "$SCRIPTS_DIR/synology_task.sh"

echo "==> Verifying Python 3..."
python3 --version

echo "==> Test run (dry-run: just aggregates, does not push)..."
cd "$REPO_DIR"
python3 scripts/aggregate.py
echo "    summary.json written to: $REPO_DIR/docs/data/summary.json"

echo ""
echo "==> Setup complete."
echo ""
echo "Next step — add to DSM Task Scheduler:"
echo "  Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script"
echo "  Task name:  CISD Hub Aggregator"
echo "  User:       root"
echo "  Schedule:   Daily at 20:00"
echo "  Script:     bash $SCRIPTS_DIR/synology_task.sh"
echo ""
echo "Manual test run:"
echo "  bash $SCRIPTS_DIR/synology_task.sh"
