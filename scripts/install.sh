#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ ! -d venv ]; then
    echo "Oppretter virtualenv..."
    python3 -m venv venv
fi

echo "Installerer avhengigheter..."
venv/bin/pip install --upgrade pip --quiet
venv/bin/pip install -r requirements-dev.txt --quiet

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Opprettet .env fra .env.example — husk å fylle inn CLAUDE_USAGE_COOKIE og CLAUDE_USAGE_API_URL før du starter appen."
fi

echo "Installerer og starter LaunchAgent for autostart..."
"$REPO_DIR/scripts/install_launch_agent.sh"

echo "Ferdig. Appen kjører nå og starter automatisk ved fremtidig pålogging."
