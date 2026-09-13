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
    fetch_usage,
)


@dataclass(frozen=True)
class Account:
    key: str
    """Stabil identitet på tvers av omstarter — brukes til å huske aktivt valg."""

    label: str
    """Visningsnavn i menyen, typisk plantypen: «Pro», «Max», «Team Plan»."""

    cookie: str
    api_url: str

    cookie_env_key: str
    """Nøkkelen denne cookien faktisk står under i .env.

    En gammel .env bruker CLAUDE_USAGE_COOKIE, en nummerert bruker
    CLAUDE_USAGE_ACCOUNT_2_COOKIE — hjelpeteksten må navngi den riktige.
    """

    api_url_env_key: str


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


def _fetch_one(
    account: Account, previous: AccountUsage | None, now: datetime
) -> AccountUsage:
    try:
        usage = fetch_usage(account.cookie, account.api_url)
    except UsageAuthError:
        return _failure(account, previous, "Cookien utløpt – oppdater", actionable=True)
    except UsageFetchError as exc:
        return _failure(account, previous, str(exc), actionable=True)
    except Exception as exc:
        return _failure(account, previous, f"Uventet feil: {exc}", actionable=False)

    return AccountUsage(account=account, usage=usage, updated_at=now)


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
