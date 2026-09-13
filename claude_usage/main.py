from __future__ import annotations

import functools
import math
import shutil
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import objc
import rumps
from AppKit import (
    NSApplication,
    NSApplicationActivationPolicyAccessory,
    NSBezierPath,
    NSColor,
    NSFont,
    NSFontWeightRegular,
    NSTextAlignmentRight,
    NSTextField,
    NSView,
)
from Foundation import NSMakeRect
from PyObjCTools import AppHelper

from claude_usage import __version__, config
from claude_usage.accounts import Account, AccountUsage, fetch_all, resolve_active

REFRESH_INTERVAL_SECONDS = 60
LAUNCH_AGENT_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "local.claude-usage.plist"
LAUNCH_AGENT_LABEL = "local.claude-usage"
APP_BUNDLE_PATH = Path.home() / "Applications" / "Claude Usage.app"
THRESHOLD_PERCENT = 90

WEEKDAY_ABBREVIATIONS = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]

# Kolonnene i en målerrad, i punkter. Innrykket lar raden flukte med
# vanlige menyelementer; summen av alle kolonnene er bredden på menyen,
# siden målerraden er den bredeste den inneholder.
MENU_TEXT_INSET = 21.0
METER_LABEL_WIDTH = 52.0
METER_BAR_WIDTH = 69.0
METER_BAR_HEIGHT = 4.0
METER_PERCENT_GAP = 8.0
METER_PERCENT_WIDTH = 44.0
METER_COUNTDOWN_WIDTH = 92.0
METER_ROW_TRAILING = 14.0
METER_ROW_MIN_HEIGHT = 22.0
METER_ROW_WIDTH = (
    MENU_TEXT_INSET
    + METER_LABEL_WIDTH
    + METER_BAR_WIDTH
    + METER_PERCENT_GAP
    + METER_PERCENT_WIDTH
    + METER_COUNTDOWN_WIDTH
    + METER_ROW_TRAILING
)

# Stolpen tegnes i systemets tekstfarge med lav metning, så den holder
# seg rolig ved siden av teksten i både lys og mørk modus.
BAR_TRACK_ALPHA = 0.12
BAR_FILL_ALPHA = 0.6
BAR_MUTED_FACTOR = 0.5

# Nedtellingen står i mindre skrift enn resten av raden.
SECONDARY_FONT_DELTA = 1.5


class MeterBar(NSView):
    """Stolpen i en målerrad.

    Tegnes for hånd i stedet for å settes som farge på et lag: `drawRect_`
    kalles med visningens gjeldende utseende, så systemfargene følger et
    bytte mellom lys og mørk modus uten at menyen bygges på nytt.
    """

    def initWithFrame_(self, frame):
        self = objc.super(MeterBar, self).initWithFrame_(frame)
        if self is None:
            return None
        self.percent = 0
        self.critical = False
        self.muted = False
        return self

    def drawRect_(self, _dirty):
        bounds = self.bounds()
        radius = bounds.size.height / 2.0
        dimming = BAR_MUTED_FACTOR if self.muted else 1.0

        NSColor.labelColor().colorWithAlphaComponent_(
            BAR_TRACK_ALPHA * dimming
        ).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, radius, radius
        ).fill()

        share = max(0.0, min(1.0, self.percent / 100.0))
        if share == 0:
            return

        if self.critical and not self.muted:
            fill_color = NSColor.systemRedColor()
        else:
            fill_color = NSColor.labelColor().colorWithAlphaComponent_(
                BAR_FILL_ALPHA * dimming
            )
        fill_color.setFill()
        # Et fyll smalere enn stolpen er høy blir en flis. En liten prosent
        # skal likevel synes, så det minste vi tegner er en prikk.
        width = max(bounds.size.height, bounds.size.width * share)
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0, 0, width, bounds.size.height), radius, radius
        ).fill()


class MeterLine:
    """Feltene i én målerrad, samlet så raden kan oppdateres uten å bygges
    på nytt: etikett, stolpe, prosent og nedtelling i faste kolonner."""

    def __init__(self, view, label, bar, percent, countdown):
        self.view = view
        self.label = label
        self.bar = bar
        self.percent = percent
        self.countdown = countdown

    def update(self, *, label, percent, countdown, critical, muted, tooltip):
        self.label.setStringValue_(label)
        self.percent.setStringValue_(format_percent(percent))
        self.countdown.setStringValue_(countdown or "")
        self.view.setToolTip_(tooltip)

        text_color = NSColor.secondaryLabelColor() if muted else NSColor.labelColor()
        self.label.setTextColor_(text_color)
        self.percent.setTextColor_(
            NSColor.systemRedColor() if critical and not muted else text_color
        )
        self.countdown.setTextColor_(
            NSColor.tertiaryLabelColor() if muted else NSColor.secondaryLabelColor()
        )

        self.bar.percent = percent
        self.bar.critical = critical
        self.bar.muted = muted
        self.bar.setNeedsDisplay_(True)


def make_meter_line() -> MeterLine:
    """En menylinje vi tegner selv, for tall som bare skal leses.

    Et vanlig menyelement er enten påskrudd — og får blå markering ved
    mouse-over, som lover en handling som ikke finnes — eller avslått, og
    da grår macOS ut teksten uansett hvilken farge vi ber om. Et element
    med egen visning slipper begge deler: det markeres aldri, og fargen
    er vår.
    """
    font = NSFont.menuFontOfSize_(0)
    small_font = NSFont.menuFontOfSize_(font.pointSize() - SECONDARY_FONT_DELTA)
    # Tabulære sifre: prosentkolonnen skal stå stille når tallet endrer seg.
    figure_font = NSFont.monospacedDigitSystemFontOfSize_weight_(
        font.pointSize(), NSFontWeightRegular
    )

    height = max(METER_ROW_MIN_HEIGHT, _text_height(font) + 6.0)
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, METER_ROW_WIDTH, height))
    baseline = (height - _text_height(font)) / 2.0 - font.descender()

    label = _place_field(view, font, MENU_TEXT_INSET, METER_LABEL_WIDTH, baseline)

    bar_x = MENU_TEXT_INSET + METER_LABEL_WIDTH
    bar = MeterBar.alloc().initWithFrame_(
        NSMakeRect(
            bar_x,
            round((height - METER_BAR_HEIGHT) / 2.0),
            METER_BAR_WIDTH,
            METER_BAR_HEIGHT,
        )
    )
    view.addSubview_(bar)

    percent_x = bar_x + METER_BAR_WIDTH + METER_PERCENT_GAP
    percent = _place_field(view, figure_font, percent_x, METER_PERCENT_WIDTH, baseline)
    percent.setAlignment_(NSTextAlignmentRight)

    countdown = _place_field(
        view,
        small_font,
        percent_x + METER_PERCENT_WIDTH,
        METER_COUNTDOWN_WIDTH,
        baseline,
    )
    countdown.setAlignment_(NSTextAlignmentRight)

    return MeterLine(view, label, bar, percent, countdown)


def _text_height(font) -> float:
    return math.ceil(font.ascender() - font.descender())


def _place_field(container, font, x: float, width: float, baseline: float) -> NSTextField:
    """Et tekstfelt i en fast kolonne, satt på en felles grunnlinje.

    Kolonnene har ulik skriftstørrelse. Uten felles grunnlinje ville
    nedtellingen flyte over eller under prosenten i samme rad.
    """
    field = NSTextField.labelWithString_("")
    field.setFont_(font)
    field.setFrame_(
        NSMakeRect(x, baseline + font.descender(), width, _text_height(font))
    )
    container.addSubview_(field)
    return field


def format_title(session: int, weekly: int, threshold: int) -> str:
    session_str = f"{session}!" if session >= threshold else f"{session}"
    weekly_str = f"{weekly}!" if weekly >= threshold else f"{weekly}"
    return f"{session_str} · {weekly_str}"


def format_percent(percent: int) -> str:
    # Smalt hardt mellomrom: tallet og prosenttegnet skal aldri skilles.
    return f"{percent}\u202f%"


def format_meter(label: str, percent: int, countdown: str | None) -> str:
    """Hele raden som én streng – det skjermlesere og testene leser."""
    if countdown is None:
        return f"{label} {format_percent(percent)}"
    return f"{label} {format_percent(percent)} · {countdown}"


def format_countdown(resets_at: datetime | None, now: datetime) -> str | None:
    if resets_at is None:
        return None

    delta = resets_at - now

    if delta <= timedelta(minutes=1):
        return "nå"
    if delta < timedelta(hours=1):
        return f"om {int(delta.total_seconds() // 60)} min"
    if delta < timedelta(hours=24):
        hours, minutes = divmod(int(delta.total_seconds() // 60), 60)
        return f"om {hours} t {minutes} min"
    return f"om {round(delta.total_seconds() / 86400)} d"


def format_reset_at(resets_at: datetime | None, now: datetime) -> str | None:
    """Klokkeslettet for nullstillingen – ligger i verktøytipset på raden.

    Ukedagen tas med først når nullstillingen ligger så langt fram at
    klokkeslettet alene er tvetydig.
    """
    if resets_at is None:
        return None

    local = resets_at.astimezone()
    if resets_at - now < timedelta(hours=24):
        return f"Nullstilles {local:%H:%M}"
    return f"Nullstilles {WEEKDAY_ABBREVIATIONS[local.weekday()]} {local:%H:%M}"


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
        self.weekly_meter = rumps.MenuItem(f"uke-{account.key}", callback=None)

        self.session_line = make_meter_line()
        self.session_meter._menuitem.setView_(self.session_line.view)
        self.weekly_line = make_meter_line()
        self.weekly_meter._menuitem.setView_(self.weekly_line.view)
        self.end_separator = rumps.rumps.SeparatorMenuItem()

        for item in (self.header, self.error, self.stale):
            item.hidden = True
        # Menyen styrer av/på selv (autoenablesItems=False), så alt som
        # ikke skal kunne klikkes må slås av eksplisitt — også mens det
        # er skjult.
        for item in (self.error, self.stale, self.session_meter, self.weekly_meter):
            item._menuitem.setEnabled_(False)

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
            (f"konto:{self.key}:uke", self.weekly_meter),
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
        self.footer_item._menuitem.setEnabled_(False)
        self.error_item._menuitem.setEnabled_(False)

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
        self._set_muted_title(
            self.footer_item, format_footer(__version__, self._footer_updated_at)
        )

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
            self._set_action_title(
                group.error,
                result.error,
                functools.partial(self._show_help, result.account.key)
                if result.actionable
                else None,
            )
        else:
            group.error.hidden = True
            self._set_action_title(group.error, group.error.title, None)

        if result.usage is None:
            group.stale.hidden = True
            self._hide_meters(group)
            return

        stale = result.error is not None
        if stale:
            prefix = "Klikk for oppskrift · " if result.actionable else ""
            updated = f"{result.updated_at.astimezone():%H:%M}" if result.updated_at else "–"
            group.stale.hidden = False
            self._set_action_title(
                group.stale,
                f"{prefix}siste tall {updated}",
                functools.partial(self._show_help, result.account.key)
                if result.actionable
                else None,
            )
        else:
            group.stale.hidden = True

        # Gamle tall dempes, ferske står i full vekt.
        self._set_meter(
            group.session_meter,
            group.session_line,
            "Sesjon",
            result.usage.session_percent,
            result.usage.session_resets_at,
            now,
            muted=stale,
        )
        self._set_meter(
            group.weekly_meter,
            group.weekly_line,
            "Uke",
            result.usage.weekly_percent,
            result.usage.weekly_resets_at,
            now,
            muted=stale,
        )

    def _hide_meters(self, group: AccountMenuGroup) -> None:
        group.session_meter.hidden = True
        group.weekly_meter.hidden = True

    def _show_app_error(self, message: str, actionable: bool) -> None:
        """Feil som gjelder hele appen — i praksis «ingen kontoer i .env»."""
        self.title = "⚠️"
        self.error_item.hidden = False
        self._set_action_title(
            self.error_item, message, self._show_setup_help if actionable else None
        )
        self._set_muted_title(
            self.footer_item, format_footer(__version__, self._footer_updated_at)
        )

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
        # Uten dette slår macOS av elementer uten action ved visning, og
        # overstyrer fargen vi setter selv.
        self.menu._menu.setAutoenablesItems_(False)
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
    def _set_action_title(item, text: str, callback) -> None:
        """Klikkbar linje. Av/på følger om det finnes noe å klikke på."""
        item.title = text
        item.set_callback(callback)
        item._menuitem.setEnabled_(callback is not None)

    @staticmethod
    def _set_muted_title(item, text: str) -> None:
        """Sekundær tekst: avslått, så macOS grår den ut og den markeres ikke."""
        item.title = text
        item._menuitem.setEnabled_(False)

    @staticmethod
    def _set_meter(item, line, label, percent, resets_at, now, *, muted: bool) -> None:
        """Oppdater én målerrad.

        Nedtellingen og verktøytipset faller bort når tallene er gamle: de
        ville telt ned mot en nullstilling vi ikke lenger vet noe om.
        """
        countdown = None if muted else format_countdown(resets_at, now)
        item.hidden = False
        item.title = format_meter(label, percent, countdown)  # for tilgjengelighet og tester
        line.update(
            label=label,
            percent=percent,
            countdown=countdown,
            critical=percent >= THRESHOLD_PERCENT,
            muted=muted,
            tooltip=None if muted else format_reset_at(resets_at, now),
        )

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
