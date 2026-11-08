import threading
from datetime import datetime, timezone
from unittest.mock import patch

from claude_usage.accounts import Account, AccountUsage, fetch_all, resolve_active
from claude_usage.usage_client import UsageAuthError, UsageData, UsageFetchError

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 13, 11, 0, tzinfo=timezone.utc)

def _account(key, label, cookie):
    return Account(
        key=key,
        label=label,
        cookie=cookie,
        session_key_env_key=f"CLAUDE_USAGE_ACCOUNT_{key}_SESSION_KEY",
    )

PRO = _account("1", "Pro", "session=pro")
TEAM = _account("2", "Team Plan", "session=team")


def _usage(session=43, weekly=76):
    return UsageData(
        session_percent=session,
        weekly_percent=weekly,
        session_resets_at=None,
        weekly_resets_at=None,
    )


# --- resolve_active -------------------------------------------------------


def test_resolve_active_uses_stored_key():
    assert resolve_active([PRO, TEAM], "2") == TEAM


def test_resolve_active_falls_back_to_first_when_key_unknown():
    """Kontoen kan ha blitt fjernet fra .env siden valget ble lagret."""
    assert resolve_active([PRO, TEAM], "slettet") == PRO


def test_resolve_active_falls_back_to_first_when_no_key_stored():
    assert resolve_active([PRO, TEAM], None) == PRO


# --- fetch_all ------------------------------------------------------------


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_queries_each_account_with_its_own_credentials(mock_fetch):
    mock_fetch.return_value = _usage()

    results = fetch_all([PRO, TEAM], previous={}, now=NOW)

    assert {call.args for call in mock_fetch.call_args_list} == {
        ("session=pro", "https://usage/session=pro"),
        ("session=team", "https://usage/session=team"),
    }
    assert [r.account for r in results] == [PRO, TEAM]
    assert all(r.error is None and r.updated_at == NOW for r in results)


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_isolates_failure_to_the_failing_account(mock_fetch):
    """Utløpt cookie på én konto skal ikke skjule tallene til den andre."""
    def side_effect(cookie, _api_url):
        if cookie == "session=team":
            raise UsageAuthError("expired")
        return _usage()

    mock_fetch.side_effect = side_effect

    pro, team = fetch_all([PRO, TEAM], previous={}, now=NOW)

    assert pro.usage == _usage() and pro.error is None
    assert team.usage is None
    assert team.error == "Innlogging utløpt – oppdater sessionKey"
    assert team.actionable is True


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_keeps_previous_numbers_when_fetch_fails(mock_fetch):
    mock_fetch.side_effect = UsageAuthError("expired")
    previous = {
        "1": AccountUsage(account=PRO, usage=_usage(), updated_at=EARLIER),
    }

    (pro,) = fetch_all([PRO], previous=previous, now=NOW)

    assert pro.usage == _usage()
    assert pro.updated_at == EARLIER
    assert pro.error == "Innlogging utløpt – oppdater sessionKey"


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_reports_fetch_error_as_actionable(mock_fetch):
    mock_fetch.side_effect = UsageFetchError("Uventet HTTP-status: 400")

    (pro,) = fetch_all([PRO], previous={}, now=NOW)

    assert pro.error == "Uventet HTTP-status: 400"
    assert pro.actionable is True


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_reports_unexpected_error_as_not_actionable(mock_fetch):
    """En uventet feil fikses ikke ved å lime inn en ny cookie."""
    mock_fetch.side_effect = RuntimeError("boom")

    (pro,) = fetch_all([PRO], previous={}, now=NOW)

    assert pro.error == "Uventet feil: boom"
    assert pro.actionable is False


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_queries_accounts_concurrently(mock_fetch):
    """Barrieren løses bare hvis begge kallene er i luften samtidig — ellers
    slår timeouten inn. Gjør parallelliteten bevist, ikke antatt."""
    barrier = threading.Barrier(2, timeout=5)

    def side_effect(_cookie, _api_url):
        barrier.wait()
        return _usage()

    mock_fetch.side_effect = side_effect

    results = fetch_all([PRO, TEAM], previous={}, now=NOW)

    assert [r.error for r in results] == [None, None]


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_looks_up_the_org_once_per_cookie(mock_fetch, discover):
    mock_fetch.return_value = _usage()

    fetch_all([PRO], previous={}, now=NOW)
    fetch_all([PRO], previous={}, now=NOW)

    assert discover.call_count == 1


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_looks_up_the_org_again_after_a_failure(mock_fetch, discover):
    """Adressen kan være årsaken til feilen, så den skal ikke huskes."""
    mock_fetch.side_effect = [UsageFetchError("borte"), _usage()]

    (failed,) = fetch_all([PRO], previous={}, now=NOW)
    (ok,) = fetch_all([PRO], previous={}, now=NOW)

    assert failed.error == "borte"
    assert ok.usage == _usage()
    assert discover.call_count == 2


@patch("claude_usage.accounts.fetch_usage")
def test_fetch_all_reports_expired_login_from_org_lookup(mock_fetch, discover):
    discover.side_effect = UsageAuthError("expired")

    (pro,) = fetch_all([PRO], previous={}, now=NOW)

    assert pro.error == "Innlogging utløpt – oppdater sessionKey"
    assert pro.actionable is True
    mock_fetch.assert_not_called()
