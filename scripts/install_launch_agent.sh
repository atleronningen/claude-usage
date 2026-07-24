#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_TEMPLATE="$REPO_DIR/scripts/local.claude-usage.plist.template"
PLIST_DEST="$HOME/Library/LaunchAgents/local.claude-usage.plist"

sed -e "s#__REPO_DIR__#$REPO_DIR#g" -e "s#__HOME__#$HOME#g" "$PLIST_TEMPLATE" > "$PLIST_DEST"

launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "LaunchAgent installert og startet. Logg: $HOME/Library/Logs/claude-usage.log"
