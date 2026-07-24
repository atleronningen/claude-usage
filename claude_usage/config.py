import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import dotenv_values

CONFIG_DIR = Path.home() / ".claude-usage"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_NOTIFICATIONS_ENABLED = True


class CredentialsMissingError(Exception):
    """CLAUDE_USAGE_COOKIE eller CLAUDE_USAGE_API_URL mangler i .env."""


@dataclass
class Settings:
    notifications_enabled: bool = DEFAULT_NOTIFICATIONS_ENABLED


def load_settings() -> Settings:
    if not CONFIG_PATH.exists():
        return Settings()
    try:
        with open(CONFIG_PATH) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return Settings()
    return Settings(
        notifications_enabled=raw.get(
            "notifications_enabled", DEFAULT_NOTIFICATIONS_ENABLED
        ),
    )


def save_settings(settings: Settings) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(asdict(settings), f, indent=2)


def env_file_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def load_credentials() -> tuple[str, str]:
    file_values = dotenv_values(env_file_path())
    cookie = os.environ.get("CLAUDE_USAGE_COOKIE") or file_values.get("CLAUDE_USAGE_COOKIE")
    api_url = os.environ.get("CLAUDE_USAGE_API_URL") or file_values.get("CLAUDE_USAGE_API_URL")
    if not cookie or not api_url:
        raise CredentialsMissingError("Mangler cookie/API-URL i .env")
    return cookie, api_url
