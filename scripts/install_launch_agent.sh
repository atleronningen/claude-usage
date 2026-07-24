#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/atleronningen/Playground/claude-usage"
PLIST_SOURCE="$REPO_DIR/scripts/com.atle.claude-usage.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.atle.claude-usage.plist"

cp "$PLIST_SOURCE" "$PLIST_DEST"
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "LaunchAgent installert og startet. Logg: ~/Library/Logs/claude-usage.log"
