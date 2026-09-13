import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from AppKit import NSColor

from claude_usage import __version__
from claude_usage.accounts import Account
from claude_usage.config import CredentialsMissingError
from claude_usage.main import (
    ClaudeUsageApp,
    format_countdown,
    format_footer,
    format_meter,
    format_percent,
    format_reset_at,
    format_title,
)
from claude_usage.usage_client import UsageAuthError, UsageData, UsageFetchError

NOW = datetime(2026, 7, 24, 12, 33, 0, tzinfo=timezone.utc)

def _account(key, label, cookie, api_url):
    return Account(
        key=key,
        label=label,
        cookie=cookie,
        api_url=api_url,
        cookie_env_key=f"CLAUDE_USAGE_ACCOUNT_{key}_COOKIE",
        api_url_env_key=f"CLAUDE_USAGE_ACCOUNT_{key}_API_URL",
    )

PRO = _account("1", "Pro", "c-pro", "https://x/1/usage")
TEAM = _account("2", "Team Plan", "c-team", "https://x/2/usage")


def _local_clock(dt: datetime) -> str:
    return f"{dt.astimezone():%H:%M}"


def _usage(session=43, weekly=76, session_resets=None, weekly_resets=None):
    return UsageData(
        session_percent=session,
        weekly_percent=weekly,
        session_resets_at=session_resets,
        weekly_resets_at=weekly_resets,
    )


def _by_cookie(**mapping):
    """Lag en fetch_usage-stubb som svarer ulikt per konto.

    Verdier som er unntak kastes; alt annet returneres.
    """
    def side_effect(cookie, _api_url):
        result = mapping[cookie]
        if isinstance(result, Exception):
            raise result
        return result

    return side_effect


def _sync(fn):
    """Kjør «bakgrunnsarbeid» med én gang, i kallerens tråd.

    Appen tar planleggingen inn som en søm, så testene bruker nøyaktig
    samme kodesti som produksjon — bare uten event-loop og tråder.
    """
    fn()


@contextmanager
def _app(accounts, fetch, active_key=None):
    """Start appen med gitte kontoer og et stubbet usage-endepunkt.

    `fetch` patcher `claude_usage.accounts.fetch_usage`, altså så nær
    nettverkskanten som mulig — resten av hentestien er ekte kode.
    """
    if not callable(fetch):
        fetch = _by_cookie(**{a.cookie: fetch for a in accounts})

    with patch("claude_usage.main.config.load_accounts", return_value=accounts), \
         patch("claude_usage.main.config.load_active_account_key", return_value=active_key), \
         patch("claude_usage.main.config.save_active_account_key") as save, \
         patch("claude_usage.accounts.fetch_usage", side_effect=fetch):
        yield ClaudeUsageApp(background=_sync, on_main=_sync), save


# --- Én konto: uendret oppførsel -----------------------------------------


def test_single_account_shows_data_and_hides_error():
    with _app([PRO], _usage()) as (app, _):
        group = app._account_items["1"]

        assert app.title == "43 · 76"
        assert app.error_item.hidden is True
        assert group.error.hidden is True
        assert group.session_meter.hidden is False
        assert group.session_meter.title.startswith("Sesjon")
        assert group.weekly_meter.hidden is False
        assert app.footer_item.title.startswith("Oppdatert ")
        assert app.footer_item.title.endswith(f"App v{__version__}")


def test_single_account_hides_its_header():
    """Med bare én konto skal menyen se ut nøyaktig som før — ingen kontolinje."""
    with _app([PRO], _usage()) as (app, _):
        assert app._account_items["1"].header.hidden is True


def test_countdown_column_is_empty_when_resets_at_missing():
    with _app([PRO], _usage()) as (app, _):
        group = app._account_items["1"]
        assert group.session_line.countdown.stringValue() == ""
        assert group.weekly_line.countdown.stringValue() == ""
        assert group.session_line.view.toolTip() is None


def test_threshold_crossed_marks_title_and_meter():
    """I menylinjen er utropstegnet det eneste virkemiddelet. I menyen har
    raden farge, og da er rødt stolpe- og prosenttall tydeligere."""
    with _app([PRO], _usage(weekly=92)) as (app, _):
        group = app._account_items["1"]
        assert app.title == "43 · 92!"
        assert group.weekly_line.bar.critical is True
        assert group.weekly_line.percent.textColor() == NSColor.systemRedColor()
        assert group.session_line.bar.critical is False
        assert group.session_line.percent.textColor() == NSColor.labelColor()


def test_footer_is_never_interactive():
    with _app([PRO], _usage()) as (app, _):
        assert app.footer_item.callback is None
        assert app.footer_item._menuitem.isEnabled() is False


# --- Flere kontoer --------------------------------------------------------


def test_both_accounts_are_rendered_with_their_own_numbers():
    fetch = _by_cookie(**{"c-pro": _usage(43, 76), "c-team": _usage(12, 8)})

    with _app([PRO, TEAM], fetch) as (app, _):
        assert format_percent(43) in app._account_items["1"].session_meter.title
        assert format_percent(12) in app._account_items["2"].session_meter.title
        assert app._account_items["1"].header.title == "Pro"
        assert app._account_items["2"].header.title == "Team Plan"
        assert app._account_items["1"].header.hidden is False


def test_title_follows_the_active_account():
    fetch = _by_cookie(**{"c-pro": _usage(43, 76), "c-team": _usage(12, 8)})

    with _app([PRO, TEAM], fetch, active_key="2") as (app, _):
        assert app.title == "12 · 8"


def test_active_account_is_checked_and_others_are_not():
    fetch = _by_cookie(**{"c-pro": _usage(), "c-team": _usage()})

    with _app([PRO, TEAM], fetch, active_key="2") as (app, _):
        assert app._account_items["1"].header.state == 0
        assert app._account_items["2"].header.state == 1


def test_selecting_another_account_switches_title_and_persists_choice():
    fetch = _by_cookie(**{"c-pro": _usage(43, 76), "c-team": _usage(12, 8)})

    with _app([PRO, TEAM], fetch) as (app, save):
        assert app.title == "43 · 76"

        app._account_items["2"].header.callback(app._account_items["2"].header)

        assert app.title == "12 · 8"
        assert app._account_items["2"].header.state == 1
        assert app._account_items["1"].header.state == 0
        save.assert_called_once_with("2")


def test_accounts_with_identical_meters_both_stay_visible():
    """rumps nøkler menyelementer på tittel — to like målerlinjer må ikke
    kollidere slik at den ene stille forsvinner fra menyen."""
    fetch = _by_cookie(**{"c-pro": _usage(8, 8), "c-team": _usage(8, 8)})

    with _app([PRO, TEAM], fetch) as (app, _):
        items = list(app.menu.values())
        assert app._account_items["1"].session_meter in items
        assert app._account_items["2"].session_meter in items
        assert app._account_items["1"].session_meter.title == app._account_items["2"].session_meter.title


# --- Feil per konto -------------------------------------------------------


def test_failure_on_inactive_account_leaves_title_intact():
    fetch = _by_cookie(**{"c-pro": _usage(43, 76), "c-team": UsageAuthError("expired")})

    with _app([PRO, TEAM], fetch, active_key="1") as (app, _):
        assert app.title == "43 · 76"
        assert app._account_items["2"].error.hidden is False
        assert app._account_items["2"].error.title == "Cookien utløpt – oppdater"
        assert app._account_items["1"].error.hidden is True


def test_failure_on_active_account_shows_warning_title():
    fetch = _by_cookie(**{"c-pro": UsageAuthError("expired"), "c-team": _usage(12, 8)})

    with _app([PRO, TEAM], fetch, active_key="1") as (app, _):
        assert app.title == "⚠️"
        assert format_percent(12) in app._account_items["2"].session_meter.title


def test_fetch_error_is_actionable():
    """En UsageFetchError (f.eks. feil org-ID) skal kunne klikkes for å
    åpne oppskriften, akkurat som utløpt cookie."""
    with _app([PRO], UsageFetchError("Uventet HTTP-status: 400")) as (app, _):
        group = app._account_items["1"]
        assert group.error.title == "Uventet HTTP-status: 400"
        assert group.error.callback is not None


def test_error_before_any_data_hides_that_accounts_lines():
    with _app([PRO], UsageAuthError("expired")) as (app, _):
        group = app._account_items["1"]
        assert app.title == "⚠️"
        assert group.session_meter.hidden is True
        assert group.weekly_meter.hidden is True
        assert app.footer_item.title == f"App v{__version__}"


def test_stale_numbers_survive_a_failed_refresh():
    responses = [_usage(session_resets=datetime.now(timezone.utc) + timedelta(hours=1))]

    def fetch(_cookie, _api_url):
        if responses:
            return responses.pop()
        raise UsageAuthError("expired")

    with _app([PRO], fetch) as (app, _):
        assert app._account_items["1"].session_line.countdown.stringValue() != ""  # før feilen

        app.refresh(None)

        group = app._account_items["1"]
        assert app.title == "⚠️"
        assert group.error.title == "Cookien utløpt – oppdater"
        assert group.stale.hidden is False
        assert group.stale.title.startswith("Klikk for oppskrift · siste tall ")
        assert group.session_meter.hidden is False  # gamle tall vises fortsatt
        assert group.session_line.label.textColor() == NSColor.secondaryLabelColor()  # dempet
        assert group.session_line.countdown.stringValue() == ""  # og uten nedtelling
        assert group.session_line.view.toolTip() is None
        assert app.footer_item.title.startswith("Oppdatert ")


def test_missing_credentials_shows_app_level_error():
    with patch(
        "claude_usage.main.config.load_accounts",
        side_effect=CredentialsMissingError("Mangler cookie/API-URL i .env"),
    ), patch("claude_usage.main.config.load_active_account_key", return_value=None):
        app = ClaudeUsageApp()

    assert app.title == "⚠️"
    assert app.error_item.hidden is False
    assert app.error_item.title == "Mangler cookie/API-URL i .env"
    assert app._account_items == {}
    assert app.footer_item.title == f"App v{__version__}"


# --- Menyrebygging --------------------------------------------------------


def test_menu_is_not_rebuilt_when_account_set_is_unchanged():
    with _app([PRO], _usage()) as (app, _):
        before = app._account_items["1"].session_meter

        app.refresh(None)

        assert app._account_items["1"].session_meter is before


def test_menu_is_rebuilt_when_an_account_is_added():
    fetch = _by_cookie(**{"c-pro": _usage(), "c-team": _usage(12, 8)})

    with patch("claude_usage.main.config.load_accounts", return_value=[PRO]), \
         patch("claude_usage.main.config.load_active_account_key", return_value=None), \
         patch("claude_usage.main.config.save_active_account_key"), \
         patch("claude_usage.accounts.fetch_usage", side_effect=fetch):
        app = ClaudeUsageApp(background=_sync, on_main=_sync)
        assert set(app._account_items) == {"1"}

        with patch("claude_usage.main.config.load_accounts", return_value=[PRO, TEAM]):
            app.refresh(None)

        assert set(app._account_items) == {"1", "2"}
        assert format_percent(12) in app._account_items["2"].session_meter.title
        assert app._account_items["2"].session_meter in list(app.menu.values())


# --- Bakgrunnstråd --------------------------------------------------------


def test_fetching_happens_off_the_calling_thread():
    """Hentingen må ikke blokkere tråden menylinjen tegnes fra."""
    threads = {}

    def fetch(_cookie, _api_url):
        threads["fetch"] = threading.current_thread()
        return _usage()

    def background(fn):
        worker = threading.Thread(target=fn)
        worker.start()
        worker.join(timeout=5)

    with patch("claude_usage.main.config.load_accounts", return_value=[PRO]), \
         patch("claude_usage.main.config.load_active_account_key", return_value=None), \
         patch("claude_usage.accounts.fetch_usage", side_effect=fetch):
        ClaudeUsageApp(background=background, on_main=_sync)

    assert threads["fetch"] is not threading.current_thread()


def test_ui_updates_are_marshalled_back_to_the_main_thread():
    """Alt som rører rumps må gå gjennom on_main — AppKit er ikke trådsikkert."""
    calls = []

    def background(fn):
        worker = threading.Thread(target=fn)
        worker.start()
        worker.join(timeout=5)

    def on_main(fn):
        calls.append(threading.current_thread())
        fn()

    with patch("claude_usage.main.config.load_accounts", return_value=[PRO]), \
         patch("claude_usage.main.config.load_active_account_key", return_value=None), \
         patch("claude_usage.accounts.fetch_usage", return_value=_usage()):
        app = ClaudeUsageApp(background=background, on_main=on_main)

    assert len(calls) == 1  # rendering ble marshallet, ikke gjort i arbeidertråden
    assert app.title == "43 · 76"


def test_a_second_fetch_is_not_started_while_one_is_in_flight():
    """Treg respons skal ikke bygge opp en kø av overlappende hentinger."""
    started = []

    with patch("claude_usage.main.config.load_accounts", return_value=[PRO]), \
         patch("claude_usage.main.config.load_active_account_key", return_value=None), \
         patch("claude_usage.accounts.fetch_usage", return_value=_usage()):
        app = ClaudeUsageApp(background=started.append, on_main=_sync)

        app.refresh(None)

        assert len(started) == 1


# --- Rene formateringsfunksjoner -----------------------------------------


@pytest.mark.parametrize(
    "session, weekly, expected",
    [
        (43, 76, "43 · 76"),
        (43, 92, "43 · 92!"),
        (91, 92, "91! · 92!"),
    ],
)
def test_format_title(session, weekly, expected):
    assert format_title(session, weekly, threshold=90) == expected


def test_format_percent_keeps_number_and_sign_together():
    assert format_percent(43) == "43\u202f%"


@pytest.mark.parametrize(
    "percent, countdown, expected",
    [
        (0, None, "Sesjon 0\u202f%"),
        (43, "om 47 min", "Sesjon 43\u202f% · om 47 min"),
        (112, "nå", "Sesjon 112\u202f% · nå"),  # over 100 vises uklippet
    ],
)
def test_format_meter(percent, countdown, expected):
    assert format_meter("Sesjon", percent, countdown) == expected


def test_reset_formatters_return_none_when_missing():
    assert format_countdown(None, NOW) is None
    assert format_reset_at(None, NOW) is None


@pytest.mark.parametrize(
    "delta, expected",
    [
        (timedelta(minutes=0), "nå"),
        (timedelta(minutes=-5), "nå"),  # tidspunkt i fortiden, klippes til «nå»
        (timedelta(minutes=47), "om 47 min"),
        (timedelta(hours=1, minutes=47), "om 1 t 47 min"),
        (timedelta(days=3), "om 3 d"),
    ],
)
def test_format_countdown(delta, expected):
    assert format_countdown(NOW + delta, NOW) == expected


def test_format_reset_at_under_24_hours_is_the_clock_alone():
    resets_at = NOW + timedelta(hours=2)
    assert format_reset_at(resets_at, NOW) == f"Nullstilles {_local_clock(resets_at)}"


def test_format_reset_at_over_24_hours_includes_weekday():
    resets_at = NOW + timedelta(days=3)  # NOW er en fredag => +3 dager = mandag
    local = resets_at.astimezone()
    weekday = ["man", "tir", "ons", "tor", "fre", "lør", "søn"][local.weekday()]
    assert format_reset_at(resets_at, NOW) == f"Nullstilles {weekday} {local:%H:%M}"


def test_format_footer_without_timestamp():
    assert format_footer("0.2.0", None) == "App v0.2.0"


def test_format_footer_with_timestamp():
    updated_at = datetime(2026, 7, 24, 12, 3, tzinfo=timezone.utc)
    assert format_footer("0.2.0", updated_at) == f"Oppdatert {_local_clock(updated_at)} · App v0.2.0"


def test_last_account_does_not_add_a_second_separator_before_the_actions():
    """Hver kontoseksjon avsluttes med et skille, men handlingene har sitt
    eget — uten dette står det to streker på rad nederst."""
    fetch = _by_cookie(**{"c-pro": _usage(), "c-team": _usage()})

    with _app([PRO, TEAM], fetch) as (app, _):
        assert app._account_items["1"].end_separator._menuitem.isHidden() is False
        assert app._account_items["2"].end_separator._menuitem.isHidden() is True


def test_reading_lines_are_not_clickable():
    """Ingen av avlesningslinjene skal love en handling ved mouse-over.
    Footeren er avslått; målerne tegner seg selv, og menyelementer med
    egen visning markeres aldri."""
    resets = datetime.now(timezone.utc) + timedelta(hours=2)

    with _app([PRO], _usage(session_resets=resets)) as (app, _):
        group = app._account_items["1"]
        assert app.footer_item._menuitem.isEnabled() is False
        for item in (group.session_meter, group.weekly_meter):
            assert item._menuitem.view() is not None, item.title


def test_lines_that_do_something_stay_clickable():
    fetch = _by_cookie(**{"c-pro": _usage(), "c-team": _usage()})

    with _app([PRO, TEAM], fetch) as (app, _):
        assert app._account_items["1"].header._menuitem.isEnabled() is True
        assert app._account_items["2"].header._menuitem.isEnabled() is True
        assert app.uninstall_item._menuitem.isEnabled() is True
        assert app.quit_item._menuitem.isEnabled() is True


def test_meters_render_in_full_weight_text():
    """macOS demper avslåtte elementer uansett farge i attributtstrengen.
    Derfor tegnes målerne i en egen visning, der fargen faktisk gjelder."""
    resets = datetime.now(timezone.utc) + timedelta(hours=2)

    with _app([PRO], _usage(session_resets=resets)) as (app, _):
        line = app._account_items["1"].session_line
        assert line.label.textColor() == NSColor.labelColor()
        assert line.percent.textColor() == NSColor.labelColor()
        assert line.countdown.textColor() == NSColor.secondaryLabelColor()


def test_meter_columns_hold_the_same_values_as_the_title():
    """Tittelen er det skjermlesere og tester leser. Kolonnene er det
    brukeren ser – de to må fortelle det samme."""
    resets = datetime.now(timezone.utc) + timedelta(hours=2)

    with _app([PRO], _usage(session=43, session_resets=resets)) as (app, _):
        line = app._account_items["1"].session_line
        title = app._account_items["1"].session_meter.title
        assert line.label.stringValue() == "Sesjon"
        assert line.percent.stringValue() == format_percent(43)
        assert line.bar.percent == 43
        assert title == format_meter("Sesjon", 43, line.countdown.stringValue())


def test_absolute_reset_time_moves_to_the_tooltip():
    """Raden viser nedtellingen. Klokkeslettet er fortsatt tilgjengelig,
    men koster ikke en egen linje."""
    resets = datetime.now(timezone.utc) + timedelta(hours=2)

    with _app([PRO], _usage(session_resets=resets)) as (app, _):
        line = app._account_items["1"].session_line
        assert line.countdown.stringValue().startswith("om ")
        assert line.view.toolTip() == f"Nullstilles {resets.astimezone():%H:%M}"


def test_stale_meters_are_muted_to_signal_old_numbers():
    responses = [_usage()]

    def fetch(_cookie, _api_url):
        if responses:
            return responses.pop()
        raise UsageAuthError("expired")

    with _app([PRO], fetch) as (app, _):
        assert app._account_items["1"].session_line.label.textColor() == NSColor.labelColor()

        app.refresh(None)

        line = app._account_items["1"].session_line
        assert line.label.textColor() == NSColor.secondaryLabelColor()
        assert line.countdown.textColor() == NSColor.tertiaryLabelColor()
        assert line.bar.muted is True
