from __future__ import annotations

import functools
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import rumps
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from PyObjCTools import AppHelper

from claude_usage import __version__, config
from claude_usage.accounts import Account, AccountUsage, fetch_all, resolve_active

REFRESH_INTERVAL_SECONDS = 60
LAUNCH_AGENT_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "local.claude-usage.plist"
LAUNCH_AGENT_LABEL = "local.claude-usage"
APP_BUNDLE_PATH = Path.home() / "Applications" / "Claude Usage.app"
THRESHOLD_PERCENT = 90

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


def _run_in_background(fn) -> None:
    threading.Thread(target=fn, daemon=True).start()


def _run_on_main(fn) -> None:
    """AppKit er ikke trådsikkert — enhver UI-endring må hit først."""
    AppHelper.callAfter(fn)


class AccountMenuGroup:
    """Menylinjene for én konto.

    Elementene lages én gang og gjenbrukes: rumps holder en callback-tabell
    som aldri ryddes, så nye MenuItems hvert minutt ville lekket.
    """

    def __init__(self, account: Account, on_select, on_help):
        self.key = account.key
        self.on_help = on_help

        self.header = rumps.MenuItem(
            account.label, callback=functools.partial(on_select, account.key)
        )
        self.error = rumps.MenuItem(f"feil-{account.key}", callback=None)
        self.stale = rumps.MenuItem(f"gamle-tall-{account.key}", callback=None)
        self.session_meter = rumps.MenuItem(f"sesjon-{account.key}", callback=None)
        self.session_reset = rumps.MenuItem(f"sesjon-nullstilling-{account.key}", callback=None)
        self.mid_separator = rumps.rumps.SeparatorMenuItem()
        self.weekly_meter = rumps.MenuItem(f"uke-{account.key}", callback=None)
        self.weekly_reset = rumps.MenuItem(f"uke-nullstilling-{account.key}", callback=None)
        self.end_separator = rumps.rumps.SeparatorMenuItem()

        for item in (self.header, self.error, self.stale):
            item.hidden = True

    def entries(self) -> list[tuple[str, object]]:
        """(menynøkkel, element) i visningsrekkefølge.

        Eksplisitte nøkler er nødvendige: rumps nøkler ellers på tittelen, og
        `Menu.__setitem__` dropper duplikater stille — to kontoer med samme
        etikett eller samme målerverdi ville gjort den ene usynlig.
        """
        return [
            (f"konto:{self.key}:header", self.header),
            (f"konto:{self.key}:feil", self.error),
            (f"konto:{self.key}:gamle-tall", self.stale),
            (f"konto:{self.key}:sesjon", self.session_meter),
            (f"konto:{self.key}:sesjon-nullstilling", self.session_reset),
            (f"konto:{self.key}:midtskille", self.mid_separator),
            (f"konto:{self.key}:uke", self.weekly_meter),
            (f"konto:{self.key}:uke-nullstilling", self.weekly_reset),
            (f"konto:{self.key}:slutt", self.end_separator),
        ]


class ClaudeUsageApp(rumps.App):
    def __init__(self, *, background=_run_in_background, on_main=_run_on_main):
        super().__init__(
            "Claude Usage",
            title="…",
            quit_button=None,
        )
        self._background = background
        self._on_main = on_main
        self._fetch_in_flight = False

        self._account_items: dict[str, AccountMenuGroup] = {}
        self._accounts_by_key: dict[str, Account] = {}
        self._last_by_key: dict[str, AccountUsage] = {}
        self._last_results: list[AccountUsage] = []
        self._menu_signature: tuple | None = None
        self._footer_updated_at: datetime | None = None

        # Brukerens valg leses én gang. Leste vi det hvert minutt, kunne en
        # ekstern skriving overstyre et klikk midt i økten.
        self._active_key = config.load_active_account_key()

        self.error_item = rumps.MenuItem("Feil", callback=None)
        self.error_item.hidden = True
        self.actions_separator = rumps.rumps.SeparatorMenuItem()
        self.uninstall_item = rumps.MenuItem("Avinstaller", callback=self._uninstall)
        self.quit_item = rumps.MenuItem("Avslutt", callback=rumps.quit_application)
        self.footer_separator = rumps.rumps.SeparatorMenuItem()
        self.footer_item = rumps.MenuItem(format_footer(__version__, None), callback=None)

        self._rebuild_menu([])

        self.timer = rumps.Timer(self.refresh, REFRESH_INTERVAL_SECONDS)
        self.timer.start()

        self.refresh(None)

    # --- Hentesyklus -----------------------------------------------------

    def refresh(self, _sender) -> None:
        try:
            accounts = config.load_accounts()
        except config.CredentialsMissingError as exc:
            self._show_app_error(str(exc), actionable=True)
            return
        except Exception as exc:
            self._show_app_error(f"Uventet feil: {exc}", actionable=False)
            return

        self._accounts_by_key = {account.key: account for account in accounts}
        self._sync_menu(accounts)

        if self._fetch_in_flight:
            return
        self._fetch_in_flight = True

        previous = dict(self._last_by_key)
        now = datetime.now(timezone.utc)
        self._background(lambda: self._fetch_worker(accounts, previous, now))

    def _fetch_worker(self, accounts, previous, now) -> None:
        """Kjører i bakgrunnstråd. Rører aldri rumps."""
        results = fetch_all(accounts, previous, now)
        self._on_main(lambda: self._apply(results))

    def _apply(self, results: list[AccountUsage]) -> None:
        """Kjører på hovedtråden. All UI-endring skjer her eller nedenfor."""
        self._fetch_in_flight = False
        self._last_by_key = {result.account.key: result for result in results}
        self._last_results = results
        self.error_item.hidden = True
        self._render(results)

    # --- Rendering -------------------------------------------------------

    def _render(self, results: list[AccountUsage]) -> None:
        if not results:
            return

        accounts = [result.account for result in results]
        active = resolve_active(accounts, self._active_key)
        show_header = len(accounts) > 1
        now = datetime.now(timezone.utc)

        for index, result in enumerate(results):
            group = self._account_items.get(result.account.key)
            if group is None:
                continue  # kontoen forsvant fra .env mens hentingen pågikk
            self._render_account(
                group,
                result,
                now,
                is_active=result.account.key == active.key,
                show_header=show_header,
                # Siste konto avsluttes av handlingsskillet under, ellers
                # står to streker på rad.
                show_separator=show_header and index < len(results) - 1,
            )

        active_result = next(r for r in results if r.account.key == active.key)
        if active_result.error is not None or active_result.usage is None:
            self.title = "⚠️"
        else:
            self.title = format_title(
                active_result.usage.session_percent,
                active_result.usage.weekly_percent,
                THRESHOLD_PERCENT,
            )

        self._footer_updated_at = active_result.updated_at
        self.footer_item.title = format_footer(__version__, self._footer_updated_at)

    def _render_account(
        self,
        group: AccountMenuGroup,
        result: AccountUsage,
        now: datetime,
        *,
        is_active: bool,
        show_header: bool,
        show_separator: bool,
    ) -> None:
        group.header.hidden = not show_header
        group.header.title = result.account.label
        group.header.state = 1 if is_active else 0
        group.end_separator._menuitem.setHidden_(not show_separator)

        if result.error is not None:
            group.error.hidden = False
            group.error.title = result.error
            group.error.set_callback(
                functools.partial(self._show_help, result.account.key)
                if result.actionable
                else None
            )
        else:
            group.error.hidden = True
            group.error.set_callback(None)

        if result.usage is None:
            group.stale.hidden = True
            self._hide_meters(group)
            return

        stale = result.error is not None
        if stale:
            prefix = "Klikk for oppskrift · " if result.actionable else ""
            updated = f"{result.updated_at.astimezone():%H:%M}" if result.updated_at else "–"
            group.stale.title = f"{prefix}siste tall {updated}"
            group.stale.hidden = False
            group.stale.set_callback(
                functools.partial(self._show_help, result.account.key)
                if result.actionable
                else None
            )
        else:
            group.stale.hidden = True

        # Dempet tekst signaliserer «gamle tall»: rumps grår ut ethvert
        # MenuItem med callback=None.
        meter_callback = None if stale else self._noop

        group.session_meter.hidden = False
        group.session_meter.title = format_meter(
            "Sesjon", result.usage.session_percent, THRESHOLD_PERCENT
        )
        group.session_meter.set_callback(meter_callback)
        group.weekly_meter.hidden = False
        group.weekly_meter.title = format_meter(
            "Uke", result.usage.weekly_percent, THRESHOLD_PERCENT
        )
        group.weekly_meter.set_callback(meter_callback)

        session_reset = None if stale else format_reset(result.usage.session_resets_at, now)
        group.session_reset.hidden = session_reset is None
        if session_reset is not None:
            group.session_reset.title = session_reset

        weekly_reset = None if stale else format_reset(result.usage.weekly_resets_at, now)
        group.weekly_reset.hidden = weekly_reset is None
        if weekly_reset is not None:
            group.weekly_reset.title = weekly_reset

        group.mid_separator._menuitem.setHidden_(stale)

    def _hide_meters(self, group: AccountMenuGroup) -> None:
        group.session_meter.hidden = True
        group.session_meter.set_callback(None)
        group.session_reset.hidden = True
        group.weekly_meter.hidden = True
        group.weekly_meter.set_callback(None)
        group.weekly_reset.hidden = True
        group.mid_separator._menuitem.setHidden_(True)

    def _show_app_error(self, message: str, actionable: bool) -> None:
        """Feil som gjelder hele appen — i praksis «ingen kontoer i .env»."""
        self.title = "⚠️"
        self.error_item.hidden = False
        self.error_item.title = message
        self.error_item.set_callback(self._show_setup_help if actionable else None)
        self.footer_item.title = format_footer(__version__, self._footer_updated_at)

    # --- Meny ------------------------------------------------------------

    def _sync_menu(self, accounts: list[Account]) -> None:
        """Bygg menyen på nytt kun når kontosettet faktisk har endret seg."""
        signature = tuple((account.key, account.label) for account in accounts)
        if signature == self._menu_signature:
            return

        self._account_items = {
            account.key: self._account_items.get(account.key)
            or AccountMenuGroup(account, self._select_account, self._show_help)
            for account in accounts
        }
        self._rebuild_menu(accounts)
        self._menu_signature = signature

    def _rebuild_menu(self, accounts: list[Account]) -> None:
        # `self.menu = [...]` legger til i stedet for å erstatte, så clear()
        # er nødvendig. clear() beholder samme NSMenu, som statuslinjen
        # allerede peker på — derfor er dette trygt på en kjørende app.
        self.menu.clear()
        self.menu["app-feil"] = self.error_item
        for account in accounts:
            for key, item in self._account_items[account.key].entries():
                self.menu[key] = item
        self.menu["handlinger-skille"] = self.actions_separator
        self.menu["avinstaller"] = self.uninstall_item
        self.menu["avslutt"] = self.quit_item
        self.menu["footer-skille"] = self.footer_separator
        self.menu["footer"] = self.footer_item

    def _select_account(self, account_key: str, _sender) -> None:
        self._active_key = account_key
        config.save_active_account_key(account_key)
        self._render(self._last_results)

    @staticmethod
    def _noop(_sender) -> None:
        return None

    # --- Handlinger ------------------------------------------------------

    def _uninstall(self, _sender) -> None:
        response = rumps.alert(
            title="Avinstaller Claude Usage",
            message=(
                "Dette fjerner autostart-oppsettet (LaunchAgent) og app-ikonet "
                "i ~/Applications. Prosjektmappen og .env beholdes. Appen "
                "avsluttes etterpå."
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
            message="LaunchAgent og app-ikon er fjernet.",
        )

        if plist_existed:
            subprocess.run(
                ["launchctl", "remove", LAUNCH_AGENT_LABEL],
                capture_output=True,
            )
        rumps.quit_application()

    def _show_help(self, account_key: str, _sender) -> None:
        account = self._accounts_by_key.get(account_key)
        if account is None:
            self._show_setup_help(_sender)
            return

        subprocess.run(["open", "-e", str(config.env_file_path())])
        rumps.alert(
            title=f"Slik fornyer du cookien for «{account.label}»",
            message=(
                f"Logg inn som {account.label} i nettleseren først — hver konto\n"
                "har sin egen cookie.\n\n"
                "1. Åpne claude.ai/settings/usage i nettleseren\n"
                "2. Åpne utviklerverktøy (⌘+⌥+I) → Network-fanen\n"
                "3. Last siden på nytt, klikk på \"usage\"-forespørselen\n"
                "4. Under Headers → Request Headers: kopier hele Cookie-verdien\n"
                f"   og lim inn i {account.cookie_env_key}\n"
                "5. Under Headers: kopier feltet Request URL (øverst) og lim\n"
                f"   inn i {account.api_url_env_key}\n"
                "6. Lagre .env-filen som nettopp åpnet seg — appen henter\n"
                "   automatisk på nytt innen ett minutt"
            ),
        )

    def _show_setup_help(self, _sender) -> None:
        subprocess.run(["open", "-e", str(config.env_file_path())])
        rumps.alert(
            title="Slik setter du opp en konto",
            message=(
                "1. Åpne claude.ai/settings/usage i nettleseren\n"
                "2. Åpne utviklerverktøy (⌘+⌥+I) → Network-fanen\n"
                "3. Last siden på nytt, klikk på \"usage\"-forespørselen\n"
                "4. Under Headers → Request Headers: kopier hele Cookie-verdien\n"
                "   og lim inn i CLAUDE_USAGE_ACCOUNT_1_COOKIE\n"
                "5. Under Headers: kopier feltet Request URL (øverst) og lim\n"
                "   inn i CLAUDE_USAGE_ACCOUNT_1_API_URL\n"
                "6. Gi kontoen et navn i CLAUDE_USAGE_ACCOUNT_1_LABEL, f.eks. Pro\n\n"
                "Flere kontoer: gjenta med ACCOUNT_2, ACCOUNT_3 osv."
            ),
        )


def main() -> None:
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    ClaudeUsageApp().run()


if __name__ == "__main__":
    main()
