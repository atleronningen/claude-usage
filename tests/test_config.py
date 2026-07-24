import json

import pytest

from claude_usage import config


def test_load_settings_returns_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")

    settings = config.load_settings()

    assert settings == config.Settings(refresh_interval_minutes=5, notifications_enabled=True)


def test_save_then_load_settings_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")

    config.save_settings(config.Settings(refresh_interval_minutes=15, notifications_enabled=False))
    loaded = config.load_settings()

    assert loaded == config.Settings(refresh_interval_minutes=15, notifications_enabled=False)


def test_load_settings_falls_back_to_defaults_for_missing_keys(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}))
    monkeypatch.setattr(config, "CONFIG_PATH", config_path)

    settings = config.load_settings()

    assert settings == config.Settings(refresh_interval_minutes=5, notifications_enabled=True)


def test_load_credentials_returns_cookie_and_url(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLAUDE_USAGE_COOKIE=session=abc\n"
        "CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/org/usage\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    cookie, api_url = config.load_credentials()

    assert cookie == "session=abc"
    assert api_url == "https://claude.ai/api/organizations/org/usage"


def test_load_credentials_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    with pytest.raises(config.CredentialsMissingError):
        config.load_credentials()
