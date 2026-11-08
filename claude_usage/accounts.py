"""Kontobegrepet: hvem vi henter forbruk for, og hva hentingen ga.

Holdt utenfor `config.py` (som handler om å lese filer) og
`usage_client.py` (som er statsløs og bare kjenner ett HTTP-kall).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

from claude_usage.usage_client import (
    UsageAuthError,
    UsageData,
    UsageFetchError,
    discover_usage_url,
    fetch_usage,
)


@dataclass(frozen=True)
class Account:
    key: str
    """Stabil identitet på tvers av omstarter — brukes til å huske aktivt valg."""

    label: str
    """Visningsnavn i menyen, typisk plantypen: «Pro», «Max», «Team Plan»."""

    cookie: str
    """Cookie-headeren som sendes, typisk bare `sessionKey=sk-ant-…`."""

    session_key_env_key: str
    """Nøkkelen hjelpeteksten ber brukeren lime sessionKey inn i.

    En gammel unummerert .env bruker CLAUDE_USAGE_SESSION_KEY, en nummerert
    CLAUDE_USAGE_ACCOUNT_2_SESSION_KEY – teksten må navngi den riktige.
    """


@dataclass(frozen=True)
class AccountUsage:
    """Resultatet av én hentingsrunde for én konto.

    `usage` og `error` satt samtidig betyr «gamle tall, ny feil» — tallene
    vises fortsatt, men dempet og uten nullstillingslinjer.
    """

    account: Account
    usage: UsageData | None = None
    error: str | None = None
    actionable: bool = False
    updated_at: datetime | None = None


def resolve_active(accounts: list[Account], stored_key: str | None) -> Account:
    """Kontoen menylinjetittelen skal vise.

    Faller tilbake til den første kontoen både ved første oppstart og når
    et lagret valg peker på en konto som siden er fjernet fra .env.
    """
    for account in accounts:
        if account.key == stored_key:
            return account
    return accounts[0]


_usage_urls: dict[str, str] = {}
"""Usage-adressen per cookie, så organisasjonen ikke slås opp hvert minutt.

Nøklet på cookien: en ny sessionKey i .env gir automatisk nytt oppslag.
Hver konto skrives bare fra sin egen tråd, og dict-operasjoner er atomiske
under GIL, så parallelle hentinger trenger ingen lås.
"""


def _usage_url(cookie: str) -> str:
    url = _usage_urls.get(cookie)
    if url is None:
        url = discover_usage_url(cookie)
        _usage_urls[cookie] = url
    return url


def _fetch_one(
    account: Account, previous: AccountUsage | None, now: datetime
) -> AccountUsage:
    try:
        usage = fetch_usage(account.cookie, _usage_url(account.cookie))
    except Exception as exc:
        # Slå opp organisasjonen på nytt neste runde – adressen kan være
        # årsaken til feilen.
        _usage_urls.pop(account.cookie, None)
        return _fetch_failure(account, previous, exc)

    return AccountUsage(account=account, usage=usage, updated_at=now)


def _fetch_failure(
    account: Account, previous: AccountUsage | None, exc: Exception
) -> AccountUsage:
    if isinstance(exc, UsageAuthError):
        message, actionable = "Innlogging utløpt – oppdater sessionKey", True
    elif isinstance(exc, UsageFetchError):
        message, actionable = str(exc), True
    else:
        message, actionable = f"Uventet feil: {exc}", False
    return _failure(account, previous, message, actionable=actionable)


def _failure(
    account: Account, previous: AccountUsage | None, message: str, actionable: bool
) -> AccountUsage:
    """Behold forrige runde sine tall, så menyen ikke går tom ved en blipp."""
    return AccountUsage(
        account=account,
        usage=previous.usage if previous else None,
        error=message,
        actionable=actionable,
        updated_at=previous.updated_at if previous else None,
    )


def fetch_all(
    accounts: list[Account],
    previous: dict[str, AccountUsage],
    now: datetime,
) -> list[AccountUsage]:
    """Hent forbruk for alle kontoer parallelt.

    Kaster aldri og rører ingen UI-tilstand, så den er trygg å kalle fra en
    bakgrunnstråd. Parallelliseringen gjør at total ventetid er én timeout,
    ikke én per konto.
    """
    with ThreadPoolExecutor(max_workers=len(accounts)) as executor:
        return list(
            executor.map(
                lambda account: _fetch_one(account, previous.get(account.key), now),
                accounts,
            )
        )
