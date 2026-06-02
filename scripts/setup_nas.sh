#!/bin/bash
# CISD Hub — One-time NAS setup (run over SSH after robocopy, see README)
#
# Usage:
#   bash /volume1/document/CISD-Hub-Public/scripts/setup_nas.sh <GITHUB_TOKEN>
#
# The token needs Contents read+write on ryantbyc/cisd-hub-public.
# Create at: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained.

set -eu

GITHUB_TOKEN="${1:-}"
ENV_FILE="/volume1/docker/cisd-hub/.env"
SCRIPTS_DIR="/volume1/docker/cisd-hub/scripts"
LOG_DIR="/volume1/docker/cisd-hub/logs"
SCRIPT_SRC="/volume1/document/CISD-Hub-Public/scripts/synology_task.sh"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Usage: bash setup_nas.sh <github_personal_access_token>"
    exit 1
fi

echo "==> Creating directories..."
mkdir -p "$SCRIPTS_DIR" "$LOG_DIR"

echo "==> Writing token to $ENV_FILE ..."
cat > "$ENV_FILE" <<EOF
GITHUB_TOKEN=$GITHUB_TOKEN
EOF
chmod 600 "$ENV_FILE"

echo "==> Copying task script..."
cp "$SCRIPT_SRC" "$SCRIPTS_DIR/synology_task.sh"
chmod +x "$SCRIPTS_DIR/synology_task.sh"

echo "==> Verifying Python 3..."
python3 --version

echo "==> Test run (fetches live data, pushes to GitHub)..."
python3 /volume1/document/CISD-Hub-Public/scripts/aggregate.py --push
echo "    Done."

echo ""
echo "==> Setup complete. Add to DSM Task Scheduler:"
echo "  Task name:  CISD Hub Aggregator"
echo "  User:       root"
echo "  Schedule:   Daily at 20:00"
echo "  Script:     bash $SCRIPTS_DIR/synology_task.sh"
