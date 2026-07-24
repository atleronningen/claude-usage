from dataclasses import dataclass

from curl_cffi import requests


class UsageAuthError(Exception):
    """Cookien er utløpt eller ugyldig (401/403 fra usage-API-et)."""


class UsageFetchError(Exception):
    """Henting eller tolkning av usage-responsen feilet."""


@dataclass(frozen=True)
class UsageData:
    session_percent: int
    weekly_percent: int


def fetch_usage(cookie: str, api_url: str) -> UsageData:
    try:
        response = requests.get(
            api_url, headers={"Cookie": cookie}, impersonate="chrome", timeout=10
        )
    except requests.exceptions.RequestException as exc:
        raise UsageFetchError(f"Nettverksfeil ved henting av usage-data: {exc}") from exc

    if response.status_code in (401, 403):
        raise UsageAuthError(f"Cookien er utløpt ({response.status_code})")

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        raise UsageFetchError(f"Uventet HTTP-status: {response.status_code}") from exc

    try:
        data = response.json()
        return _parse_usage(data)
    except (ValueError, KeyError, TypeError) as exc:
        raise UsageFetchError(f"Kunne ikke tolke usage-responsen: {exc}") from exc


def _parse_usage(data: dict) -> UsageData:
    session_percent = round(data["five_hour"]["utilization"])
    weekly_percent = round(data["seven_day"]["utilization"])
    return UsageData(session_percent=session_percent, weekly_percent=weekly_percent)
