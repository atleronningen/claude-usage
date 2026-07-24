import shutil
import subprocess
from pathlib import Path

import rumps

from claude_usage import config
from claude_usage.notifier import ThresholdNotifier
from claude_usage.usage_client import UsageAuthError, UsageFetchError, fetch_usage

REFRESH_INTERVAL_SECONDS = 60
LAUNCH_AGENT_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.atle.claude-usage.plist"


class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__(
            "Claude Usage",
            title="…",
            quit_button=rumps.MenuItem("Avslutt"),
        )
        self.settings = config.load_settings()
        self.notifier = ThresholdNotifier()

        self.error_item = rumps.MenuItem("Ingen feil", callback=self._show_help)
        self.refresh_item = rumps.MenuItem("Oppdater nå", callback=self.refresh)
        self.notifications_item = rumps.MenuItem(
            "Varsle ved 90%", callback=self._toggle_notifications
        )
        self.notifications_item.state = self.settings.notifications_enabled
        self.uninstall_item = rumps.MenuItem("Avinstaller", callback=self._uninstall)

        self.menu = [
            self.error_item,
            None,
            self.refresh_item,
            self.notifications_item,
            None,
            self.uninstall_item,
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
            self._show_error(str(exc))
            return
        except UsageAuthError:
            self._show_error("Cookien utløpt – oppdater")
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
        self.title = "⚠️"
        self.error_item.title = message

    def _uninstall(self, _sender) -> None:
        response = rumps.alert(
            title="Avinstaller Claude Usage",
            message=(
                "Dette fjerner autostart-oppsettet (LaunchAgent) og lagrede "
                "innstillinger. Prosjektmappen og .env beholdes. Appen "
                "avsluttes etterpå."
            ),
            ok="Avinstaller",
            cancel="Avbryt",
        )
        if response != 1:
            return

        if LAUNCH_AGENT_PLIST_PATH.exists():
            subprocess.run(
                ["launchctl", "unload", str(LAUNCH_AGENT_PLIST_PATH)],
                capture_output=True,
            )
            LAUNCH_AGENT_PLIST_PATH.unlink()

        if config.CONFIG_DIR.exists():
            shutil.rmtree(config.CONFIG_DIR)

        rumps.alert(
            title="Avinstallert",
            message="LaunchAgent og lagrede innstillinger er fjernet.",
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
