#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$HOME/Applications/Claude Usage.app"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

VERSION="$("$REPO_DIR/venv/bin/python" -c "from claude_usage import __version__; print(__version__)" 2>/dev/null || echo "0.0.0")"

cat > "$CONTENTS_DIR/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Claude Usage</string>
    <key>CFBundleDisplayName</key>
    <string>Claude Usage</string>
    <key>CFBundleIdentifier</key>
    <string>local.claude-usage.launcher</string>
    <key>CFBundleExecutable</key>
    <string>claude-usage-launcher</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
PLIST

cp "$REPO_DIR/scripts/assets/claude-usage.icns" "$RESOURCES_DIR/AppIcon.icns"

cat > "$MACOS_DIR/claude-usage-launcher" <<'SCRIPT'
#!/usr/bin/env bash
LABEL="local.claude-usage"
TARGET="gui/$(id -u)/$LABEL"

if launchctl print "$TARGET" >/dev/null 2>&1; then
    launchctl kickstart -k "$TARGET"
else
    launchctl load "$HOME/Library/LaunchAgents/$LABEL.plist"
fi

osascript -e 'display notification "Appen er startet på nytt." with title "Claude Usage"' >/dev/null 2>&1 || true
SCRIPT

chmod +x "$MACOS_DIR/claude-usage-launcher"

echo "App-ikon installert: $APP_DIR"
