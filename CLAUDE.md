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
  for én konto (statsløs, kjenner ikke kontobegrepet)
- `claude_usage/accounts.py` — `Account`/`AccountUsage` og parallell henting
  for alle kontoer (`fetch_all`), samt oppløsning av aktiv konto
- `claude_usage/config.py` — kontoer fra .env (`load_accounts`) og aktivt
  kontovalg i `~/.claude-usage/state.json`
- `claude_usage/main.py` — rumps-appen (menylinje-UI)
- `scripts/` — LaunchAgent-plist og installasjonsskript
- `.env` (gitignored) — én blokk per konto:
  `CLAUDE_USAGE_ACCOUNT_<N>_LABEL` / `_COOKIE` / `_API_URL`, se `.env.example`.
  Gamle unummererte `CLAUDE_USAGE_COOKIE`/`CLAUDE_USAGE_API_URL` tolkes som
  én konto, så eksisterende oppsett virker uendret.

Hentingen kjører i bakgrunnstråd. Alt som rører rumps skjer i `_apply` og
metodene den kaller, marshallet tilbake til hovedtråden med
`AppHelper.callAfter` — AppKit er ikke trådsikkert.

LaunchAgent-plisten (`~/Library/LaunchAgents/local.claude-usage.plist`) får
prosjektmappens absolutte sti hardkodet av `install_launch_agent.sh` ved
installasjon. Flyttes prosjektmappen, må `./install` kjøres på nytt fra den
nye plasseringen for at autostart/app-ikonet skal fungere igjen.

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
