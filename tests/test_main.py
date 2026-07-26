from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from claude_usage import __version__
from claude_usage.config import CredentialsMissingError
from claude_usage.main import (
    ClaudeUsageApp,
    format_footer,
    format_meter,
    format_reset,
    format_title,
)
from claude_usage.usage_client import UsageAuthError, UsageData, UsageFetchError

NOW = datetime(2026, 7, 24, 12, 33, 0, tzinfo=timezone.utc)


def _local_clock(dt: datetime) -> str:
    return f"{dt.astimezone():%H:%M}"


def test_footer_shows_version():
    with patch(
        "claude_usage.main.config.load_credentials",
        side_effect=CredentialsMissingError("mangler"),
    ):
        app = ClaudeUsageApp()

    assert app.footer_item.title == f"App v{__version__}"


def _usage(session=43, weekly=76, session_resets=None, weekly_resets=None):
    return UsageData(
        session_percent=session,
        weekly_percent=weekly,
        session_resets_at=session_resets,
        weekly_resets_at=weekly_resets,
    )


def test_normal_state_shows_data_and_hides_error():
    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch("claude_usage.main.fetch_usage", return_value=_usage()):
        app = ClaudeUsageApp()

    assert app.title == "43 · 76"
    assert app.error_item.hidden is True
    assert app.help_item.hidden is True
    assert app.session_meter_item.hidden is False
    assert app.session_meter_item.title.startswith("Sesjon")
    assert app.weekly_meter_item.hidden is False
    assert app.footer_item.title.startswith("Oppdatert ")
    assert app.footer_item.title.endswith(f"App v{__version__}")


def test_normal_state_hides_reset_line_when_resets_at_missing():
    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch("claude_usage.main.fetch_usage", return_value=_usage()):
        app = ClaudeUsageApp()

    assert app.session_reset_item.hidden is True
    assert app.weekly_reset_item.hidden is True


def test_threshold_crossed_marks_title_and_meter():
    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch("claude_usage.main.fetch_usage", return_value=_usage(weekly=92)):
        app = ClaudeUsageApp()

    assert app.title == "43 · 92!"
    assert app.weekly_meter_item.title.endswith("92%!")


def test_error_state_before_any_fetch_hides_all_data_lines():
    with patch(
        "claude_usage.main.config.load_credentials",
        side_effect=CredentialsMissingError("mangler"),
    ):
        app = ClaudeUsageApp()

    assert app.title == "⚠️"
    assert app.error_item.hidden is False
    assert app.error_item.title == "mangler"
    assert app.help_item.hidden is True
    assert app.session_meter_item.hidden is True
    assert app.weekly_meter_item.hidden is True
    assert app.footer_item.title == f"App v{__version__}"


def test_fetch_error_is_actionable():
    """En UsageFetchError (f.eks. HTTP 400 pga. feil org-ID i .env) skal
    kunne klikkes for å åpne oppskriften, akkurat som utløpt cookie."""
    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch(
             "claude_usage.main.fetch_usage",
             side_effect=UsageFetchError("Uventet HTTP-status: 400"),
         ):
        app = ClaudeUsageApp()

    assert app.error_item.title == "Uventet HTTP-status: 400"
    assert app.error_item.callback is not None


def test_error_state_with_prior_data_shows_stale_meters_without_resets():
    responses = [_usage(session_resets=datetime.now(timezone.utc) + timedelta(hours=1))]

    def fetch_side_effect(*args, **kwargs):
        if responses:
            return responses.pop()
        raise UsageAuthError("expired")

    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch("claude_usage.main.fetch_usage", side_effect=fetch_side_effect):
        app = ClaudeUsageApp()
        assert app.session_reset_item.hidden is False  # sanity check før feilen inntreffer

        app.refresh(None)  # andre kall: responses er tom, kaster UsageAuthError

    assert app.title == "⚠️"
    assert app.error_item.hidden is False
    assert app.error_item.title == "Cookien utløpt – oppdater"
    assert app.help_item.hidden is False
    assert app.help_item.title.startswith("Klikk for oppskrift · siste tall ")
    assert app.session_meter_item.hidden is False  # gamle tall vises fortsatt
    assert app.session_reset_item.hidden is True  # men uten nullstillingslinje
    assert app.footer_item.title.startswith("Oppdatert ")


def test_normal_state_meter_items_are_not_dimmed():
    """Målerlinjene («Sesjon 43%») skal se ut som fullvekt/mørk tekst i
    normaltilstand — det krever en reell callback, siden rumps grår ut
    ethvert MenuItem med callback=None (dokumentert i rumps.set_callback)."""
    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch("claude_usage.main.fetch_usage", return_value=_usage()):
        app = ClaudeUsageApp()

    assert app.session_meter_item.callback is not None
    assert app.weekly_meter_item.callback is not None
    # Nullstillingslinjer og footer skal derimot alltid være dempet
    assert app.session_reset_item.callback is None
    assert app.weekly_reset_item.callback is None
    assert app.footer_item.callback is None


def test_error_state_meter_items_are_dimmed():
    """I feiltilstand (gamle tall) skal målerlinjene se dempet ut, i
    kontrast til normaltilstand."""
    responses = [_usage()]

    def fetch_side_effect(*args, **kwargs):
        if responses:
            return responses.pop()
        raise UsageAuthError("expired")

    with patch("claude_usage.main.config.load_credentials", return_value=("c", "u")), \
         patch("claude_usage.main.fetch_usage", side_effect=fetch_side_effect):
        app = ClaudeUsageApp()
        assert app.session_meter_item.callback is not None  # normaltilstand: ikke dempet

        app.refresh(None)  # andre kall: responses er tom, kaster UsageAuthError

    assert app.session_meter_item.callback is None
    assert app.weekly_meter_item.callback is None


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


@pytest.mark.parametrize(
    "percent, filled_cells, suffix",
    [
        (0, 0, ""),
        (4, 0, ""),
        (5, 0, ""),  # round(0.5) = 0 i Python (banker's rounding) — bevisst dokumentert her
        (43, 4, ""),
        (89, 9, ""),
        (90, 9, "!"),
        (100, 10, "!"),
        (112, 10, "!"),  # klippes til 10 celler, prosenttallet vises uklippet
    ],
)
def test_format_meter(percent, filled_cells, suffix):
    result = format_meter("Sesjon", percent, threshold=90)
    assert result == f"{'Sesjon':<7}{'▰' * filled_cells}{'▱' * (10 - filled_cells)} {percent}%{suffix}"


def test_format_reset_returns_none_when_missing():
    assert format_reset(None, NOW) is None


@pytest.mark.parametrize(
    "delta, expected_relative",
    [
        (timedelta(minutes=0), "nå"),
        (timedelta(minutes=-5), "nå"),  # tidspunkt i fortiden, klippes til «nå»
        (timedelta(minutes=47), "om 47 min"),
        (timedelta(hours=1, minutes=47), "om 1 t 47 min"),
    ],
)
def test_format_reset_under_24_hours(delta, expected_relative):
    resets_at = NOW + delta
    result = format_reset(resets_at, NOW)
    assert result == f"Nullstilles {_local_clock(resets_at)} ({expected_relative})"


def test_format_reset_over_24_hours_includes_weekday():
    resets_at = NOW + timedelta(days=3)  # NOW er en fredag => +3 dager = mandag
    result = format_reset(resets_at, NOW)
    local = resets_at.astimezone()
    weekday = ["man", "tir", "ons", "tor", "fre", "lør", "søn"][local.weekday()]
    assert result == f"Nullstilles {weekday} {local:%H:%M} (om 3 d)"


def test_format_footer_without_timestamp():
    assert format_footer("0.2.0", None) == "App v0.2.0"


def test_format_footer_with_timestamp():
    updated_at = datetime(2026, 7, 24, 12, 3, tzinfo=timezone.utc)
    assert format_footer("0.2.0", updated_at) == f"Oppdatert {_local_clock(updated_at)} · App v0.2.0"
