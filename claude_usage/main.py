from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import rumps

from claude_usage import __version__, config
from claude_usage.notifier import THRESHOLD_PERCENT, ThresholdNotifier
from claude_usage.usage_client import UsageAuthError, UsageData, UsageFetchError, fetch_usage

REFRESH_INTERVAL_SECONDS = 60
LAUNCH_AGENT_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "local.claude-usage.plist"
LAUNCH_AGENT_LABEL = "local.claude-usage"
APP_BUNDLE_PATH = Path.home() / "Applications" / "Claude Usage.app"

METER_CELLS = 10
METER_FILLED = "▰"
METER_EMPTY = "▱"
WEEKDAY_ABBREVIATIONS = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]


def format_title(session: int, weekly: int, threshold: int) -> str:
    session_str = f"{session}!" if session >= threshold else f"{session}"
    weekly_str = f"{weekly}!" if weekly >= threshold else f"{weekly}"
    return f"{session_str} · {weekly_str}"


def format_meter(label: str, percent: int, threshold: int) -> str:
    filled = max(0, min(METER_CELLS, round(percent / 10)))
    bar = METER_FILLED * filled + METER_EMPTY * (METER_CELLS - filled)
    suffix = "!" if percent >= threshold else ""
    return f"{label:<7}{bar} {percent}%{suffix}"


def format_reset(resets_at: datetime | None, now: datetime) -> str | None:
    if resets_at is None:
        return None

    local = resets_at.astimezone()
    delta = resets_at - now

    if delta <= timedelta(minutes=1):
        return f"Nullstilles {local:%H:%M} (nå)"
    if delta < timedelta(hours=1):
        minutes = int(delta.total_seconds() // 60)
        return f"Nullstilles {local:%H:%M} (om {minutes} min)"
    if delta < timedelta(hours=24):
        total_minutes = int(delta.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"Nullstilles {local:%H:%M} (om {hours} t {minutes} min)"

    weekday = WEEKDAY_ABBREVIATIONS[local.weekday()]
    days = round(delta.total_seconds() / 86400)
    return f"Nullstilles {weekday} {local:%H:%M} (om {days} d)"


def format_footer(version: str, updated_at: datetime | None) -> str:
    if updated_at is None:
        return f"App v{version}"
    return f"Oppdatert {updated_at.astimezone():%H:%M} · App v{version}"


class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Claude Usage",
            title="…",
            quit_button=rumps.MenuItem("Avslutt"),
        )
        self.settings = config.load_settings()
        self.notifier = ThresholdNotifier()

        self.error_item = rumps.MenuItem("Ingen feil", callback=None)
        self.refresh_item = rumps.MenuItem("Oppdater nå", callback=self.refresh)
        self.notifications_item = rumps.MenuItem(
            "Varsle ved 90%", callback=self._toggle_notifications
        )
        self.notifications_item.state = self.settings.notifications_enabled
        self.uninstall_item = rumps.MenuItem("Avinstaller", callback=self._uninstall)
        self.version_item = rumps.MenuItem(f"v{__version__}", callback=None)

        self.menu = [
            self.error_item,
            None,
            self.refresh_item,
            self.notifications_item,
            None,
            self.uninstall_item,
            None,
            self.version_item,
        ]

        self.timer = rumps.Timer(self.refresh, REFRESH_INTERVAL_SECONDS)
        self.timer.start()

        self.refresh(None)

    def _toggle_notifications(self, sender) -> None:
        self.settings.notifications_enabled = not self.settings.notifications_enabled
        sender.state = self.settings.notifications_enabled
        config.save_settings(self.settings)

    def refresh(self, _sender) -> None:
        try:
            cookie, api_url = config.load_credentials()
            usage = fetch_usage(cookie, api_url)
        except config.CredentialsMissingError as exc:
            self._show_error(str(exc), actionable=True)
            return
        except UsageAuthError:
            self._show_error("Cookien utløpt – oppdater", actionable=True)
            return
        except UsageFetchError as exc:
            self._show_error(str(exc), actionable=False)
            return
        except Exception as exc:
            self._show_error(f"Uventet feil: {exc}", actionable=False)
            return

        self.title = f"S:{usage.session_percent}% U:{usage.weekly_percent}%"
        self.error_item.title = "Ingen feil"
        self.error_item.set_callback(None)
        self.notifier.check(
            usage.session_percent, usage.weekly_percent, self.settings.notifications_enabled
        )

    def _show_error(self, message: str, actionable: bool = False) -> None:
        self.title = "⚠️"
        self.error_item.title = message
        self.error_item.set_callback(self._show_help if actionable else None)

    def _uninstall(self, _sender) -> None:
        response = rumps.alert(
            title="Avinstaller Claude Usage",
            message=(
                "Dette fjerner autostart-oppsettet (LaunchAgent), app-ikonet "
                "i ~/Applications, og lagrede innstillinger. Prosjektmappen "
                "og .env beholdes. Appen avsluttes etterpå."
            ),
            ok="Avinstaller",
            cancel="Avbryt",
        )
        if response != 1:
            return

        plist_existed = LAUNCH_AGENT_PLIST_PATH.exists()
        if plist_existed:
            LAUNCH_AGENT_PLIST_PATH.unlink()

        if APP_BUNDLE_PATH.exists():
            shutil.rmtree(APP_BUNDLE_PATH)

        if config.CONFIG_DIR.exists():
            shutil.rmtree(config.CONFIG_DIR)

        rumps.alert(
            title="Avinstallert",
            message="LaunchAgent, app-ikon og lagrede innstillinger er fjernet.",
        )

        if plist_existed:
            subprocess.run(
                ["launchctl", "remove", LAUNCH_AGENT_LABEL],
                capture_output=True,
            )
        rumps.quit_application()

    def _show_help(self, _sender) -> None:
        subprocess.run(["open", "-e", str(config.env_file_path())])
        rumps.alert(
            title="Slik henter du en fersk cookie",
            message=(
                "1. Åpne claude.ai/settings/usage i nettleseren\n"
                "2. Åpne utviklerverktøy (⌘+⌥+I) → Network-fanen\n"
                "3. Last siden på nytt, klikk på \"usage\"-forespørselen\n"
                "4. Under Headers → Request Headers: kopier hele Cookie-verdien\n"
                "5. Lim inn i CLAUDE_USAGE_COOKIE i .env-filen som nettopp åpnet seg\n"
                "6. Lagre filen, og klikk \"Oppdater nå\" i menyen"
            ),
        )


def main() -> None:
    ClaudeUsageApp().run()


if __name__ == "__main__":
    main()
