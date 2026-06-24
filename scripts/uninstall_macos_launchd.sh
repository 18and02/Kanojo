#!/usr/bin/env bash
set -euo pipefail

LABEL="${LABEL:-com.kanojo.backend}"
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Kanojo}"
BACKEND_DIR="$PROJECT_ROOT/backend"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER="$BACKEND_DIR/.launchd/run_backend.sh"

launchctl bootout "gui/$UID" "$PLIST" >/dev/null 2>&1 || true
launchctl bootout "gui/$UID/$LABEL" >/dev/null 2>&1 || true

rm -f "$PLIST"
rm -f "$WRAPPER"

echo "Uninstalled $LABEL"
