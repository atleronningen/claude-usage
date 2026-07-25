# Claude Usage — for Claude

Menylinje-app (macOS) som gir status på tokenforbruk for Claude.
Mappenavn: claude-usage.

## Stack

Python 3, rumps (menylinje-UI), curl_cffi, python-dotenv, pytest (dev).

`curl_cffi` brukes i stedet for `requests` fordi claude.ai sitt
usage-API er bak Cloudflare-beskyttelse som blokkerer på TLS-fingerprint
— se kommentaren i `usage_client.py` for detaljer.

## Kommandoer

- Installer avhengigheter: `venv/bin/pip install -r requirements-dev.txt`
- Kjør tester: `venv/bin/python -m pytest`
- Kjør appen manuelt: `venv/bin/python -m claude_usage.main`
- Full nyinstallasjon (venv + avhengigheter + .env + autostart): `./install` (peker til `scripts/install.sh`)
- Installer autostart (LaunchAgent): `./scripts/install_launch_agent.sh`

## Struktur

- `claude_usage/usage_client.py` — henter og parser usage-data fra claude.ai
- `claude_usage/config.py` — credentials (.env)
- `claude_usage/main.py` — rumps-appen (menylinje-UI)
- `scripts/` — LaunchAgent-plist og installasjonsskript
- `.env` (gitignored) — `CLAUDE_USAGE_COOKIE` og `CLAUDE_USAGE_API_URL`, se `.env.example`

## Versjonering

Semantisk versjonering (`MAJOR.MINOR.PATCH`). `__version__` i
`claude_usage/__init__.py` er eneste kilde til sannhet, og vises i
menylinjens dropdown-meny.

- Legg til punkter under `## [Unreleased]` i `CHANGELOG.md` fortløpende
  når funksjonalitet legges til, endres eller fjernes.
- Kjør `./scripts/release.sh X.Y.Z` for å kutte en ny versjon. Scriptet
  flytter Unreleased-innholdet til en datert seksjon, bumper
  `__version__`, committer, tagger, pusher og oppretter en GitHub
  Release. Krever rent arbeidstre og at `main` er oppdatert med
  `origin/main`.
- Rollback: `git checkout vX.Y.Z` og restart appen.
