import textwrap

import rumps

from claude_usage import config
from claude_usage.notifier import ThresholdNotifier
from claude_usage.usage_client import UsageAuthError, UsageFetchError, fetch_usage

REFRESH_INTERVAL_SECONDS = 60


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
        self.notifications_item = rumps.MenuItem(
            "Varsle ved 90%", callback=self._toggle_notifications
        )
        self.notifications_item.state = self.settings.notifications_enabled

        self.menu = [self.error_item, None, self.refresh_item, self.notifications_item]

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
        self.title = "⚠️"
        self.error_item.title = textwrap.fill(message, width=50)


def main() -> None:
    ClaudeUsageApp().run()


if __name__ == "__main__":
    main()
