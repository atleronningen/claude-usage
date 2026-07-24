# Claude Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bygg en macOS-menylinje-app (Claude Usage) som viser Atles forbruk av Claude.ai-abonnementet (session- og ukentlig grense) og varsler ved 90 %.

**Architecture:** Python-app med `rumps` for menylinje-UI, en `rumps.Timer` som poller claude.ai sitt interne usage-API med et konfigurerbart intervall, og en macOS LaunchAgent for autostart ved pålogging. Fire small moduler: `usage_client.py` (henting/parsing), `config.py` (credentials + innstillinger), `notifier.py` (terskelvarsling), `main.py` (rumps-app som binder alt sammen).

**Tech Stack:** Python 3, `rumps`, `requests`, `python-dotenv`, `pytest` (dev).

## Global Constraints

- Kun for personlig bruk på Atles egen Mac — ingen distribusjon/signering.
- Én datakilde: `claude.ai`s interne usage-API (udokumentert). Ingen Anthropic Admin API, ingen lokal Claude Code-logg-parsing.
- Ingen kostnadsestimat i kr/$ vises — kun prosentandel av session- og ukegrense.
- Cookien lagres i en lokal, gitignorede `.env`-fil og limes inn manuelt av Atle ved utløp — appen skal aldri prøve å autentisere seg på annen måte.
- Feiltilstand (utløpt cookie, nettverksfeil, uventet respons) skal alltid vises tydelig (`"?"` i menylinjen + feilmelding i dropdown) — aldri vise en gammel verdi som om den var gyldig.
- Standard oppdateringsintervall: 5 minutter, valgbart mellom 1/5/15 minutter i innstillinger.
- Varsling ved ≥ 90 % skal kunne slås av/på i innstillinger, default på, og skal ikke varsle flere ganger for samme periode.
- Repo: `/Users/atleronningen/Playground/claude-usage` (allerede opprettet med git-identitet og `.gitignore`).

## Referanse: ekte API-respons

Hentet manuelt av Atle fra `claude.ai/settings/usage` sitt Network-kall
(`GET https://claude.ai/api/organizations/{org_id}/usage`). Feltene under
er de eneste vi bruker — resten av responsen (mange `null`-felt,
`extra_usage`, `spend`, osv.) er urelatert til dette prosjektet og
ignoreres bevisst (YAGNI):

```json
{
    "five_hour": {
        "utilization": 62.0,
        "resets_at": "2026-07-24T21:09:59.018485+00:00"
    },
    "seven_day": {
        "utilization": 58.0,
        "resets_at": "2026-07-28T19:59:59.018510+00:00"
    }
}
```

`five_hour.utilization` = session-grense i prosent (0–100, float).
`seven_day.utilization` = ukentlig grense i prosent (0–100, float).

---

### Task 1: Prosjektoppsett (venv, avhengigheter, pakkeskjelett)

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `claude_usage/__init__.py`
- Create: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: pakken `claude_usage` som senere tasks legger moduler i. Virtualenv i `venv/`.

- [ ] **Step 1: Opprett virtualenv**

```bash
cd /Users/atleronningen/Playground/claude-usage
python3 -m venv venv
```

- [ ] **Step 2: Opprett `requirements.txt`**

```
rumps==0.4.0
requests==2.32.3
python-dotenv==1.0.1
```

- [ ] **Step 3: Opprett `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.3
```

- [ ] **Step 4: Installer avhengigheter**

```bash
venv/bin/pip install -r requirements-dev.txt
```

Expected: installasjon fullfører uten feil.

- [ ] **Step 5: Opprett pakkeskjelett**

Opprett `claude_usage/__init__.py` med tomt innhold (gjør `claude_usage`
til en importerbar pakke).

- [ ] **Step 6: Opprett `.env.example`**

```
CLAUDE_USAGE_COOKIE=lim-inn-cookie-header-fra-devtools-her
CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/DIN-ORG-ID/usage
```

- [ ] **Step 7: Utvid `.gitignore` for Python**

Legg til følgende linjer i `.gitignore` (i tillegg til det som allerede
står der):

```
venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 8: Commit**

```bash
git add requirements.txt requirements-dev.txt claude_usage/__init__.py .env.example .gitignore
git commit -m "Sett opp prosjektskjelett for Claude Usage"
```

---

### Task 2: `usage_client.py` — henting og parsing av usage-data

**Files:**
- Create: `claude_usage/usage_client.py`
- Test: `tests/test_usage_client.py`

**Interfaces:**
- Produces:
  - `class UsageData` (dataclass): `session_percent: int`, `weekly_percent: int`
  - `class UsageAuthError(Exception)`
  - `class UsageFetchError(Exception)`
  - `def fetch_usage(cookie: str, api_url: str) -> UsageData`

- [ ] **Step 1: Skriv failende tester**

Opprett `tests/test_usage_client.py`:

```python
import pytest
import responses

from claude_usage.usage_client import (
    UsageAuthError,
    UsageData,
    UsageFetchError,
    fetch_usage,
)

API_URL = "https://claude.ai/api/organizations/test-org/usage"


def _sample_response(five_hour_utilization=62.0, seven_day_utilization=58.0):
    return {
        "five_hour": {
            "utilization": five_hour_utilization,
            "resets_at": "2026-07-24T21:09:59.018485+00:00",
        },
        "seven_day": {
            "utilization": seven_day_utilization,
            "resets_at": "2026-07-28T19:59:59.018510+00:00",
        },
    }


@responses.activate
def test_fetch_usage_parses_percentages():
    responses.add(responses.GET, API_URL, json=_sample_response(), status=200)

    usage = fetch_usage(cookie="session=abc", api_url=API_URL)

    assert usage == UsageData(session_percent=62, weekly_percent=58)


@responses.activate
def test_fetch_usage_rounds_float_percentages():
    responses.add(
        responses.GET,
        API_URL,
        json=_sample_response(five_hour_utilization=61.6, seven_day_utilization=58.4),
        status=200,
    )

    usage = fetch_usage(cookie="session=abc", api_url=API_URL)

    assert usage == UsageData(session_percent=62, weekly_percent=58)


@responses.activate
def test_fetch_usage_raises_auth_error_on_401():
    responses.add(responses.GET, API_URL, json={}, status=401)

    with pytest.raises(UsageAuthError):
        fetch_usage(cookie="session=expired", api_url=API_URL)


@responses.activate
def test_fetch_usage_raises_auth_error_on_403():
    responses.add(responses.GET, API_URL, json={}, status=403)

    with pytest.raises(UsageAuthError):
        fetch_usage(cookie="session=expired", api_url=API_URL)


@responses.activate
def test_fetch_usage_raises_fetch_error_on_server_error():
    responses.add(responses.GET, API_URL, json={}, status=500)

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)


@responses.activate
def test_fetch_usage_raises_fetch_error_on_unexpected_shape():
    responses.add(responses.GET, API_URL, json={"unexpected": "shape"}, status=200)

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)
```

Legg til `responses==0.25.3` i `requirements-dev.txt` (biblioteket for å
mocke `requests`-kall i tester), og installer på nytt:

```bash
venv/bin/pip install -r requirements-dev.txt
```

- [ ] **Step 2: Kjør testene for å bekrefte at de feiler**

```bash
venv/bin/python -m pytest tests/test_usage_client.py -v
```

Expected: FAIL med `ModuleNotFoundError: No module named 'claude_usage.usage_client'`

- [ ] **Step 3: Implementer `claude_usage/usage_client.py`**

```python
from dataclasses import dataclass

import requests


class UsageAuthError(Exception):
    """Cookien er utløpt eller ugyldig (401/403 fra usage-API-et)."""


class UsageFetchError(Exception):
    """Henting eller tolkning av usage-responsen feilet."""


@dataclass(frozen=True)
class UsageData:
    session_percent: int
    weekly_percent: int


def fetch_usage(cookie: str, api_url: str) -> UsageData:
    try:
        response = requests.get(api_url, headers={"Cookie": cookie}, timeout=10)
    except requests.RequestException as exc:
        raise UsageFetchError(f"Nettverksfeil ved henting av usage-data: {exc}") from exc

    if response.status_code in (401, 403):
        raise UsageAuthError(
            f"Autentisering feilet ({response.status_code}) — cookien er sannsynligvis utløpt"
        )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise UsageFetchError(f"Uventet HTTP-status: {response.status_code}") from exc

    try:
        data = response.json()
        return _parse_usage(data)
    except (ValueError, KeyError, TypeError) as exc:
        raise UsageFetchError(f"Kunne ikke tolke usage-responsen: {exc}") from exc


def _parse_usage(data: dict) -> UsageData:
    session_percent = round(data["five_hour"]["utilization"])
    weekly_percent = round(data["seven_day"]["utilization"])
    return UsageData(session_percent=session_percent, weekly_percent=weekly_percent)
```

- [ ] **Step 4: Kjør testene for å bekrefte at de passerer**

```bash
venv/bin/python -m pytest tests/test_usage_client.py -v
```

Expected: PASS (6 tester)

- [ ] **Step 5: Commit**

```bash
git add claude_usage/usage_client.py tests/test_usage_client.py requirements-dev.txt
git commit -m "Legg til usage_client med henting og parsing av usage-data"
```

---

### Task 3: `config.py` — credentials og innstillinger

**Files:**
- Create: `claude_usage/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `VALID_REFRESH_INTERVALS: tuple[int, ...]` = `(1, 5, 15)`
  - `class CredentialsMissingError(Exception)`
  - `@dataclass class Settings`: `refresh_interval_minutes: int = 5`, `notifications_enabled: bool = True`
  - `def load_settings() -> Settings`
  - `def save_settings(settings: Settings) -> None`
  - `def load_credentials() -> tuple[str, str]` (cookie, api_url)
- Consumes: ingenting fra tidligere tasks.

- [ ] **Step 1: Skriv failende tester**

Opprett `tests/test_config.py`:

```python
import json

import pytest

from claude_usage import config


def test_load_settings_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")

    settings = config.load_settings()

    assert settings == config.Settings(refresh_interval_minutes=5, notifications_enabled=True)


def test_save_then_load_settings_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")

    config.save_settings(config.Settings(refresh_interval_minutes=15, notifications_enabled=False))
    loaded = config.load_settings()

    assert loaded == config.Settings(refresh_interval_minutes=15, notifications_enabled=False)


def test_load_settings_falls_back_to_defaults_for_missing_keys(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}))
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    settings = config.load_settings()

    assert settings == config.Settings(refresh_interval_minutes=5, notifications_enabled=True)


def test_load_credentials_returns_cookie_and_url(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLAUDE_USAGE_COOKIE=session=abc\n"
        "CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/org/usage\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    cookie, api_url = config.load_credentials()

    assert cookie == "session=abc"
    assert api_url == "https://claude.ai/api/organizations/org/usage"


def test_load_credentials_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    with pytest.raises(config.CredentialsMissingError):
        config.load_credentials()
```

- [ ] **Step 2: Kjør testene for å bekrefte at de feiler**

```bash
venv/bin/python -m pytest tests/test_config.py -v
```

Expected: FAIL med `ModuleNotFoundError: No module named 'claude_usage.config'`

- [ ] **Step 3: Implementer `claude_usage/config.py`**

```python
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".claude-usage"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_REFRESH_INTERVAL_MINUTES = 5
DEFAULT_NOTIFICATIONS_ENABLED = True

VALID_REFRESH_INTERVALS = (1, 5, 15)


class CredentialsMissingError(Exception):
    """CLAUDE_USAGE_COOKIE eller CLAUDE_USAGE_API_URL mangler i .env."""


@dataclass
class Settings:
    refresh_interval_minutes: int = DEFAULT_REFRESH_INTERVAL_MINUTES
    notifications_enabled: bool = DEFAULT_NOTIFICATIONS_ENABLED


def load_settings() -> Settings:
    if not CONFIG_PATH.exists():
        return Settings()
    with open(CONFIG_PATH) as f:
        raw = json.load(f)
    return Settings(
        refresh_interval_minutes=raw.get(
            "refresh_interval_minutes", DEFAULT_REFRESH_INTERVAL_MINUTES
        ),
        notifications_enabled=raw.get(
            "notifications_enabled", DEFAULT_NOTIFICATIONS_ENABLED
        ),
    )


def save_settings(settings: Settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(asdict(settings), f, indent=2)


def load_credentials() -> tuple[str, str]:
    load_dotenv()
    cookie = os.environ.get("CLAUDE_USAGE_COOKIE")
    api_url = os.environ.get("CLAUDE_USAGE_API_URL")
    if not cookie or not api_url:
        raise CredentialsMissingError(
            "CLAUDE_USAGE_COOKIE og CLAUDE_USAGE_API_URL må være satt i .env"
        )
    return cookie, api_url
```

- [ ] **Step 4: Kjør testene for å bekrefte at de passerer**

```bash
venv/bin/python -m pytest tests/test_config.py -v
```

Expected: PASS (5 tester)

- [ ] **Step 5: Commit**

```bash
git add claude_usage/config.py tests/test_config.py
git commit -m "Legg til config med credentials og persisterte innstillinger"
```

---

### Task 4: `notifier.py` — terskelvarsling ved 90 %

**Files:**
- Create: `claude_usage/notifier.py`
- Test: `tests/test_notifier.py`

**Interfaces:**
- Consumes: ingenting fra tidligere tasks (bruker kun `rumps.notification`).
- Produces:
  - `THRESHOLD_PERCENT: int` = `90`
  - `class ThresholdNotifier`: `def check(self, session_percent: int, weekly_percent: int, enabled: bool) -> None`

- [ ] **Step 1: Skriv failende tester**

Opprett `tests/test_notifier.py`:

```python
from unittest.mock import patch

from claude_usage.notifier import ThresholdNotifier


def test_notifies_once_when_crossing_threshold():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=85, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 0

        notifier.check(session_percent=92, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1

        notifier.check(session_percent=93, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1  # ikke varslet på nytt


def test_notifies_again_after_percent_drops_and_rises_again():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=92, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1

        notifier.check(session_percent=10, weekly_percent=50, enabled=True)  # ny periode
        notifier.check(session_percent=91, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 2


def test_does_not_notify_when_disabled():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=95, weekly_percent=95, enabled=False)
        assert mock_notify.call_count == 0


def test_tracks_session_and_weekly_independently():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=92, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1

        notifier.check(session_percent=92, weekly_percent=91, enabled=True)
        assert mock_notify.call_count == 2
```

- [ ] **Step 2: Kjør testene for å bekrefte at de feiler**

```bash
venv/bin/python -m pytest tests/test_notifier.py -v
```

Expected: FAIL med `ModuleNotFoundError: No module named 'claude_usage.notifier'`

- [ ] **Step 3: Implementer `claude_usage/notifier.py`**

```python
import rumps

THRESHOLD_PERCENT = 90


class ThresholdNotifier:
    def __init__(self):
        self._session_notified = False
        self._weekly_notified = False

    def check(self, session_percent: int, weekly_percent: int, enabled: bool) -> None:
        if not enabled:
            return
        self._session_notified = self._check_one(
            percent=session_percent,
            already_notified=self._session_notified,
            message=f"Session-grensen er nå {session_percent}% brukt",
        )
        self._weekly_notified = self._check_one(
            percent=weekly_percent,
            already_notified=self._weekly_notified,
            message=f"Ukentlig grense er nå {weekly_percent}% brukt",
        )

    def _check_one(self, percent: int, already_notified: bool, message: str) -> bool:
        if percent < THRESHOLD_PERCENT:
            return False
        if already_notified:
            return True
        rumps.notification(title="Claude Usage", subtitle="", message=message)
        return True
```

- [ ] **Step 4: Kjør testene for å bekrefte at de passerer**

```bash
venv/bin/python -m pytest tests/test_notifier.py -v
```

Expected: PASS (4 tester)

- [ ] **Step 5: Commit**

```bash
git add claude_usage/notifier.py tests/test_notifier.py
git commit -m "Legg til notifier for terskelvarsling ved 90%"
```

---

### Task 5: `main.py` — rumps-appen

**Files:**
- Create: `claude_usage/main.py`

**Interfaces:**
- Consumes:
  - `claude_usage.config`: `Settings`, `VALID_REFRESH_INTERVALS`, `load_settings()`, `save_settings()`, `load_credentials()`, `CredentialsMissingError`
  - `claude_usage.usage_client`: `fetch_usage()`, `UsageAuthError`, `UsageFetchError`
  - `claude_usage.notifier`: `ThresholdNotifier`
- Produces: `class ClaudeUsageApp(rumps.App)`, `def main() -> None` (kjørbar via `python -m claude_usage.main`)

Denne tasken har ingen automatiserte tester — `rumps`-UI kan ikke enkelt
testes uten en faktisk macOS-menylinje-sesjon. Verifiseres manuelt i
Task 7.

- [ ] **Step 1: Implementer `claude_usage/main.py`**

```python
import rumps

from claude_usage import config
from claude_usage.notifier import ThresholdNotifier
from claude_usage.usage_client import UsageAuthError, UsageFetchError, fetch_usage


class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Claude Usage",
            title="…",
            quit_button=rumps.MenuItem("Avslutt"),
        )
        self.settings = config.load_settings()
        self.notifier = ThresholdNotifier()

        self.error_item = rumps.MenuItem("Ingen feil")
        self.refresh_item = rumps.MenuItem("Oppdater nå", callback=self.refresh)
        self.settings_menu = self._build_settings_menu()

        self.menu = [self.error_item, None, self.refresh_item, self.settings_menu]

        self.timer = rumps.Timer(self.refresh, self.settings.refresh_interval_minutes * 60)
        self.timer.start()

        self.refresh(None)

    def _build_settings_menu(self) -> rumps.MenuItem:
        self.interval_items = {}
        interval_menu = rumps.MenuItem("Oppdateringsintervall")
        for minutes in config.VALID_REFRESH_INTERVALS:
            item = rumps.MenuItem(
                f"{minutes} min", callback=self._make_interval_callback(minutes)
            )
            item.state = minutes == self.settings.refresh_interval_minutes
            interval_menu.add(item)
            self.interval_items[minutes] = item

        self.notifications_item = rumps.MenuItem(
            "Varsle ved 90%", callback=self._toggle_notifications
        )
        self.notifications_item.state = self.settings.notifications_enabled

        settings_menu = rumps.MenuItem("Innstillinger")
        settings_menu.add(interval_menu)
        settings_menu.add(self.notifications_item)
        return settings_menu

    def _make_interval_callback(self, minutes: int):
        def callback(_sender):
            self.settings.refresh_interval_minutes = minutes
            config.save_settings(self.settings)
            for item_minutes, item in self.interval_items.items():
                item.state = item_minutes == minutes
            self._restart_timer()

        return callback

    def _restart_timer(self) -> None:
        self.timer.stop()
        self.timer = rumps.Timer(self.refresh, self.settings.refresh_interval_minutes * 60)
        self.timer.start()

    def _toggle_notifications(self, sender) -> None:
        self.settings.notifications_enabled = not self.settings.notifications_enabled
        sender.state = self.settings.notifications_enabled
        config.save_settings(self.settings)

    def refresh(self, _sender) -> None:
        try:
            cookie, api_url = config.load_credentials()
            usage = fetch_usage(cookie, api_url)
        except config.CredentialsMissingError as exc:
            self._show_error(str(exc))
            return
        except UsageAuthError as exc:
            self._show_error(f"{exc} — oppdater CLAUDE_USAGE_COOKIE i .env")
            return
        except UsageFetchError as exc:
            self._show_error(str(exc))
            return

        self.title = f"S:{usage.session_percent}% U:{usage.weekly_percent}%"
        self.error_item.title = "Ingen feil"
        self.notifier.check(
            usage.session_percent, usage.weekly_percent, self.settings.notifications_enabled
        )

    def _show_error(self, message: str) -> None:
        self.title = "?"
        self.error_item.title = message


def main() -> None:
    ClaudeUsageApp().run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add claude_usage/main.py
git commit -m "Legg til rumps-app som binder usage_client, config og notifier sammen"
```

---

### Task 6: LaunchAgent — autostart ved pålogging

**Files:**
- Create: `scripts/com.atle.claude-usage.plist`
- Create: `scripts/install_launch_agent.sh`

**Interfaces:**
- Consumes: den ferdige `claude_usage`-pakken fra tasks 1–5, venv fra Task 1.

- [ ] **Step 1: Opprett `scripts/com.atle.claude-usage.plist`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atle.claude-usage</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/atleronningen/Playground/claude-usage/venv/bin/python</string>
        <string>-m</string>
        <string>claude_usage.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/atleronningen/Playground/claude-usage</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/atleronningen/Library/Logs/claude-usage.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/atleronningen/Library/Logs/claude-usage.err.log</string>
</dict>
</plist>
```

- [ ] **Step 2: Opprett `scripts/install_launch_agent.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/atleronningen/Playground/claude-usage"
PLIST_SOURCE="$REPO_DIR/scripts/com.atle.claude-usage.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.atle.claude-usage.plist"

cp "$PLIST_SOURCE" "$PLIST_DEST"
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"

echo "LaunchAgent installert og startet. Logg: ~/Library/Logs/claude-usage.log"
```

- [ ] **Step 3: Gjør skriptet kjørbart**

```bash
chmod +x scripts/install_launch_agent.sh
```

- [ ] **Step 4: Commit**

```bash
git add scripts/com.atle.claude-usage.plist scripts/install_launch_agent.sh
git commit -m "Legg til LaunchAgent for autostart ved pålogging"
```

Manuell kjøring og verifisering av selve autostarten gjøres i Task 7,
sammen med resten av ende-til-ende-testen (krever at Atle har limt inn
en gyldig cookie i `.env` først).

---

### Task 7: Oppdater CLAUDE.md og verifiser hele appen manuelt

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: hele appen fra tasks 1–6.

- [ ] **Step 1: Fyll ut CLAUDE.md-stubben**

Erstatt innholdet i `CLAUDE.md` med:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Fyll ut CLAUDE.md med stack, kommandoer og struktur"
```

- [ ] **Step 3: Kjør hele testsuiten**

```bash
venv/bin/python -m pytest -v
```

Expected: PASS (alle tester fra tasks 2–4)

- [ ] **Step 4: Manuell ende-til-ende-verifisering (krever Atle)**

Dette steget kan ikke gjøres av en agentic worker alene — det krever en
ekte, gyldig cookie fra Atles innloggede nettleser-sesjon:

1. Kopier `.env.example` til `.env` og lim inn en fersk
   `CLAUDE_USAGE_COOKIE` og `CLAUDE_USAGE_API_URL` (hentet på samme måte
   som beskrevet i spec-en: DevTools → Network → usage-forespørselen).
2. Kjør `venv/bin/python -m claude_usage.main` og bekreft at:
   - Ikonet i menylinjen viser `S:XX% U:YY%` med reelle tall.
   - Dropdown-menyen viser "Ingen feil", "Oppdater nå", "Innstillinger"
     (med undermenyene for intervall og varsling) og "Avslutt".
   - Å endre oppdateringsintervall i innstillinger huskes ved omstart av
     appen (sjekk `~/.claude-usage/config.json`).
3. Test feilhåndtering: sett en ugyldig verdi i `CLAUDE_USAGE_COOKIE`,
   klikk "Oppdater nå", og bekreft at ikonet viser `?` og at
   feilmeldingen i dropdown-menyen forklarer at cookien må oppdateres.
4. Kjør `./scripts/install_launch_agent.sh`, logg ut og inn igjen (eller
   restart Mac'en), og bekreft at appen starter automatisk.

---

## Self-review

- **Spec-dekning:** datakilde (Task 2), credentials/innstillinger
  (Task 3), varsling (Task 4), menylinje-UI med alle spesifiserte
  menypunkter (Task 5), autostart (Task 6), dokumentasjon + manuell
  verifisering av golden path og feilsti (Task 7). Alle spec-krav har en
  task.
- **Placeholder-sjekk:** ingen TBD/TODO — all kode er komplett og basert
  på det faktiske API-svaret Atle hentet ut.
- **Typekonsistens:** `UsageData(session_percent: int, weekly_percent: int)`
  brukes likt i Task 2 (produsent) og Task 5 (konsument).
  `Settings(refresh_interval_minutes: int, notifications_enabled: bool)`
  brukes likt i Task 3 og Task 5. `ThresholdNotifier.check(session_percent,
  weekly_percent, enabled)`-signaturen matcher mellom Task 4 og Task 5.
