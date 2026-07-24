import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

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


def load_credentials() -> tuple[str, str]:
    env_path = Path.cwd() / ".env"
    load_dotenv(dotenv_path=env_path)
    cookie = os.environ.get("CLAUDE_USAGE_COOKIE")
    api_url = os.environ.get("CLAUDE_USAGE_API_URL")
    if not cookie or not api_url:
        raise CredentialsMissingError(
            "CLAUDE_USAGE_COOKIE og CLAUDE_USAGE_API_URL må være satt i .env"
        )
    return cookie, api_url
