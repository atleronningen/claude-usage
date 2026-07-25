import os
from pathlib import Path

from dotenv import dotenv_values

CONFIG_DIR = Path.home() / ".claude-usage"


class CredentialsMissingError(Exception):
    """CLAUDE_USAGE_COOKIE eller CLAUDE_USAGE_API_URL mangler i .env."""


def env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def load_credentials() -> tuple[str, str]:
    file_values = dotenv_values(env_file_path())
    cookie = os.environ.get("CLAUDE_USAGE_COOKIE") or file_values.get("CLAUDE_USAGE_COOKIE")
    api_url = os.environ.get("CLAUDE_USAGE_API_URL") or file_values.get("CLAUDE_USAGE_API_URL")
    if not cookie or not api_url:
        raise CredentialsMissingError("Mangler cookie/API-URL i .env")
    return cookie, api_url
