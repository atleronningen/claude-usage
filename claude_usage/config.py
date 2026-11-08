from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import dotenv_values

from claude_usage.accounts import Account

CONFIG_DIR = Path.home() / ".claude-usage"

ACCOUNT_KEY_PATTERN = re.compile(r"^CLAUDE_USAGE_ACCOUNT_(\d+)_(LABEL|SESSION_KEY|COOKIE)$")


class CredentialsMissingError(Exception):
    """Ingen brukbar konto funnet i .env."""


def env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def state_file_path() -> Path:
    return CONFIG_DIR / "state.json"


def _settings() -> dict[str, str]:
    """Alle CLAUDE_USAGE-verdier, med shell-env foran .env-filen.

    Leses på nytt ved hvert kall, slik at en redigert .env plukkes opp uten
    at appen må startes på nytt.
    """
    values = {k: v for k, v in dotenv_values(env_file_path()).items() if v}
    for key, value in os.environ.items():
        if key.startswith("CLAUDE_USAGE_") and value:
            values[key] = value
    return values


def _cookie_header(session_key: str | None, cookie: str | None) -> str | None:
    """Cookie-headeren for én konto, eller None hvis kontoen mangler innlogging.

    `_SESSION_KEY` vinner. En hel Cookie-header (`_COOKIE`, det gamle
    formatet) virker fortsatt, siden sessionKey står inni den.
    """
    if session_key:
        session_key = session_key.strip()
        if session_key.startswith("sessionKey="):
            session_key = session_key[len("sessionKey=") :]
        return f"sessionKey={session_key}"
    return cookie or None


def load_accounts() -> list[Account]:
    """Kontoene fra .env, i nummerrekkefølge.

    Nummererte nøkler (`CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY` osv.) er
    formatet. Finnes ingen slike, tolkes de gamle unummererte nøklene som én
    konto, slik at eksisterende oppsett virker uendret. `_API_URL` leses ikke
    lenger – usage-adressen slås opp automatisk.
    """
    values = _settings()

    numbered: dict[str, dict[str, str]] = {}
    for key, value in values.items():
        match = ACCOUNT_KEY_PATTERN.match(key)
        if match:
            number, field = match.groups()
            numbered.setdefault(number, {})[field] = value

    accounts = []
    for number, fields in sorted(numbered.items(), key=lambda item: int(item[0])):
        cookie = _cookie_header(fields.get("SESSION_KEY"), fields.get("COOKIE"))
        if cookie:
            accounts.append(
                Account(
                    key=number,
                    label=fields.get("LABEL") or f"Konto {number}",
                    cookie=cookie,
                    session_key_env_key=f"CLAUDE_USAGE_ACCOUNT_{number}_SESSION_KEY",
                )
            )

    if not accounts:
        cookie = _cookie_header(
            values.get("CLAUDE_USAGE_SESSION_KEY"), values.get("CLAUDE_USAGE_COOKIE")
        )
        if cookie:
            accounts = [
                Account(
                    key="legacy",
                    label="Konto 1",
                    cookie=cookie,
                    session_key_env_key="CLAUDE_USAGE_SESSION_KEY",
                )
            ]

    if not accounts:
        raise CredentialsMissingError("Mangler sessionKey i .env")

    return accounts


def load_active_account_key() -> str | None:
    """Kontoen brukeren sist valgte, eller None hvis valget ikke kan leses.

    Et tapt valg er en bagatell — appen faller tilbake til første konto
    heller enn å krasje på en ødelagt eller utilgjengelig fil.
    """
    try:
        data = json.loads(state_file_path().read_text())
    except (OSError, ValueError):
        return None
    key = data.get("active_account_key") if isinstance(data, dict) else None
    return key if isinstance(key, str) else None


def save_active_account_key(key: str) -> None:
    path = state_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"active_account_key": key}))
    except OSError:
        pass
