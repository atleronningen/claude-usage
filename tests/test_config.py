import pytest

from claude_usage import config


def test_load_credentials_returns_cookie_and_url(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLAUDE_USAGE_COOKIE=session=abc\n"
        "CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/org/usage\n"
    )
    monkeypatch.setattr(config, "env_file_path", lambda: env_file)
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    cookie, api_url = config.load_credentials()

    assert cookie == "session=abc"
    assert api_url == "https://claude.ai/api/organizations/org/usage"


def test_load_credentials_raises_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "env_file_path", lambda: tmp_path / ".env")
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    with pytest.raises(config.CredentialsMissingError):
        config.load_credentials()


def test_load_credentials_picks_up_updated_env_file_without_restart(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLAUDE_USAGE_COOKIE=session=old\n"
        "CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/org/usage\n"
    )
    monkeypatch.setattr(config, "env_file_path", lambda: env_file)
    monkeypatch.delenv("CLAUDE_USAGE_COOKIE", raising=False)
    monkeypatch.delenv("CLAUDE_USAGE_API_URL", raising=False)

    cookie, _ = config.load_credentials()
    assert cookie == "session=old"

    env_file.write_text(
        "CLAUDE_USAGE_COOKIE=session=new\n"
        "CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/org/usage\n"
    )
    cookie, _ = config.load_credentials()
    assert cookie == "session=new"


def test_load_credentials_prefers_shell_env_over_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CLAUDE_USAGE_COOKIE=session=from-file\n"
        "CLAUDE_USAGE_API_URL=https://claude.ai/api/organizations/org/usage-from-file\n"
    )
    monkeypatch.setattr(config, "env_file_path", lambda: env_file)
    monkeypatch.setenv("CLAUDE_USAGE_COOKIE", "session=from-shell")
    monkeypatch.setenv(
        "CLAUDE_USAGE_API_URL", "https://claude.ai/api/organizations/org/usage-from-shell"
    )

    cookie, api_url = config.load_credentials()

    assert cookie == "session=from-shell"
    assert api_url == "https://claude.ai/api/organizations/org/usage-from-shell"


def test_env_file_path_ignores_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = config.env_file_path()

    assert result.name == ".env"
    assert result.parent.name == "claude-usage"
