# Claude Usage — for Claude

Menylinje-app (macOS) som gir status på tokenforbruk for Claude.
Mappenavn: claude-usage.

## Stack

Python 3, rumps (menylinje-UI), requests, python-dotenv, pytest (dev).

## Kommandoer

- Installer avhengigheter: `venv/bin/pip install -r requirements-dev.txt`
- Kjør tester: `venv/bin/python -m pytest`
- Kjør appen manuelt: `venv/bin/python -m claude_usage.main`
- Installer autostart (LaunchAgent): `./scripts/install_launch_agent.sh`

## Struktur

- `claude_usage/usage_client.py` — henter og parser usage-data fra claude.ai
- `claude_usage/config.py` — credentials (.env) og persisterte innstillinger (`~/.claude-usage/config.json`)
- `claude_usage/notifier.py` — terskelvarsling ved 90%
- `claude_usage/main.py` — rumps-appen (menylinje-UI)
- `scripts/` — LaunchAgent-plist og installasjonsskript
- `.env` (gitignored) — `CLAUDE_USAGE_COOKIE` og `CLAUDE_USAGE_API_URL`, se `.env.example`
