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

NOW = datetime(2026, 7, 24, 12, 33, 0, tzinfo=timezone.utc)


def _local_clock(dt: datetime) -> str:
    return f"{dt.astimezone():%H:%M}"


def test_menu_shows_version():
    with patch(
        "claude_usage.main.config.load_credentials",
        side_effect=CredentialsMissingError("mangler"),
    ):
        app = ClaudeUsageApp()

    assert app.version_item.title == f"v{__version__}"


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
