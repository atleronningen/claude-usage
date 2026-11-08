from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from curl_cffi import requests


class UsageAuthError(Exception):
    """Cookien er utløpt eller ugyldig (401/403 fra usage-API-et)."""


class UsageFetchError(Exception):
    """Henting eller tolkning av usage-responsen feilet."""


@dataclass(frozen=True)
class UsageData:
    session_percent: int
    weekly_percent: int
    session_resets_at: datetime | None
    weekly_resets_at: datetime | None


ORGANIZATIONS_URL = "https://claude.ai/api/organizations"


def discover_usage_url(cookie: str) -> str:
    """Usage-adressen til kontoens claude.ai-organisasjon.

    En innlogging kan høre til flere organisasjoner – en Pro-konto har ofte
    også en API-organisasjon (Console). Den gir 403 på usage, som ellers ville
    sett ut som en utløpt innlogging. Bare organisasjoner med `chat` i
    `capabilities` har forbruk på claude.ai.
    """
    data = _get_json(ORGANIZATIONS_URL, cookie)
    try:
        for org in data:
            if "chat" in (org.get("capabilities") or []):
                return f"{ORGANIZATIONS_URL}/{org['uuid']}/usage"
    except (AttributeError, KeyError, TypeError) as exc:
        raise UsageFetchError(f"Kunne ikke tolke organisasjonslista: {exc}") from exc
    raise UsageFetchError("Fant ingen claude.ai-organisasjon for kontoen")


def fetch_usage(cookie: str, api_url: str) -> UsageData:
    data = _get_json(api_url, cookie)
    try:
        return _parse_usage(data)
    except (ValueError, KeyError, TypeError) as exc:
        raise UsageFetchError(f"Kunne ikke tolke usage-responsen: {exc}") from exc


def _get_json(url: str, cookie: str):
    try:
        # claude.ai's API er bak Cloudflares bot-beskyttelse, som blokkerer
        # på TLS-fingerprint (JA3/JA4) uavhengig av om cookien er gyldig.
        # curl_cffi med impersonate="chrome" etterligner Chromes
        # TLS-fingerprint for å slippe gjennom – vanlig `requests` fungerer
        # IKKE mot disse endepunktene, selv med korrekt cookie. Det er også
        # derfor sessionKey alene holder: Cloudflare-cookiene trengs ikke.
        response = requests.get(
            url, headers={"Cookie": cookie}, impersonate="chrome", timeout=10
        )
    except requests.exceptions.CurlError as exc:
        raise UsageFetchError(f"Nettverksfeil ved henting av usage-data: {exc}") from exc

    if response.status_code in (401, 403):
        raise UsageAuthError(f"Innloggingen er utløpt ({response.status_code})")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise UsageFetchError(f"Uventet HTTP-status: {response.status_code}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise UsageFetchError(f"Kunne ikke tolke svaret fra claude.ai: {exc}") from exc


def _parse_usage(data: dict) -> UsageData:
    # Et gyldig svar uten begge seksjonene betyr at claude.ai har endret
    # formatet. Si det rett ut i stedet for en rå KeyError.
    if isinstance(data, dict) and "five_hour" not in data and "seven_day" not in data:
        raise UsageFetchError("Usage-svaret har ukjent format")
    session_percent = round(data["five_hour"]["utilization"])
    weekly_percent = round(data["seven_day"]["utilization"])
    return UsageData(
        session_percent=session_percent,
        weekly_percent=weekly_percent,
        session_resets_at=_parse_resets_at(data["five_hour"]),
        weekly_resets_at=_parse_resets_at(data["seven_day"]),
    )


def _parse_resets_at(section: dict) -> datetime | None:
    raw = section.get("resets_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
