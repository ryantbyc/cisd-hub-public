#!/bin/bash
# CISD Hub — One-time NAS setup
#
# Run this AFTER doing the 2-command bootstrap over SSH:
#
#   git clone https://<TOKEN>@github.com/ryantbyc/cisd-hub-public.git \
#       /volume1/document/CISD-Hub-Public
#   bash /volume1/document/CISD-Hub-Public/scripts/setup_nas.sh <TOKEN>
#
# The GitHub token needs: Contents read+write on ryantbyc/cisd-hub-public.
# Create at: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained.

set -eu

GITHUB_TOKEN="${1:-}"
GITHUB_USER="ryantbyc"
REPO="cisd-hub-public"
REPO_DIR="/volume1/document/CISD-Hub-Public"
LOG_DIR="/volume1/docker/cisd-hub/logs"
SCRIPTS_DIR="/volume1/docker/cisd-hub/scripts"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Usage: bash setup_nas.sh <github_personal_access_token>"
    exit 1
fi

echo "==> Creating log/script directories..."
mkdir -p "$LOG_DIR" "$SCRIPTS_DIR"

echo "==> Storing token in remote URL (credential-free push)..."
git -C "$REPO_DIR" remote set-url origin \
    "https://${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO}.git"

echo "==> Configuring git identity..."
git -C "$REPO_DIR" config user.name "CISD Hub NAS"
git -C "$REPO_DIR" config user.email "bog.graph-3v@icloud.com"

echo "==> Copying task script to persistent location..."
cp "$REPO_DIR/scripts/synology_task.sh" "$SCRIPTS_DIR/synology_task.sh"
chmod +x "$SCRIPTS_DIR/synology_task.sh"

echo "==> Verifying Python 3..."
python3 --version

echo "==> Test run (fetches live data from published sites)..."
cd "$REPO_DIR"
python3 scripts/aggregate.py
echo "    summary.json written."

echo ""
echo "==> Setup complete."
echo ""
echo "Add to DSM Task Scheduler:"
echo "  Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script"
echo "  Task name:  CISD Hub Aggregator"
echo "  User:       root"
echo "  Schedule:   Daily at 20:00 (runs 3h after finance pipeline)"
echo "  Script:     bash $SCRIPTS_DIR/synology_task.sh"
echo ""
echo "Manual test:"
echo "  bash $SCRIPTS_DIR/synology_task.sh"
