import pytest

from claude_usage import config
from claude_usage.accounts import Account

URL_1 = "https://claude.ai/api/organizations/org-1/usage"
URL_2 = "https://claude.ai/api/organizations/org-2/usage"


def _env(monkeypatch, tmp_path, contents: str):
    """Skriv en .env og pek config mot den, med et rent shell-miljø."""
    env_file = tmp_path / ".env"
    env_file.write_text(contents)
    monkeypatch.setattr(config, "env_file_path", lambda: env_file)
    for key in list(__import__("os").environ):
        if key.startswith("CLAUDE_USAGE_"):
            monkeypatch.delenv(key, raising=False)
    return env_file


# --- Nummererte kontoer ---------------------------------------------------


def test_load_accounts_parses_numbered_keys(monkeypatch, tmp_path):
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n"
        f"CLAUDE_USAGE_ACCOUNT_2_LABEL=Team Plan\n"
        f"CLAUDE_USAGE_ACCOUNT_2_COOKIE=session=team\n"
        f"CLAUDE_USAGE_ACCOUNT_2_API_URL={URL_2}\n",
    )

    accounts = config.load_accounts()

    assert accounts == [
        Account(
            key="1",
            label="Pro",
            cookie="session=pro",
            api_url=URL_1,
            cookie_env_key="CLAUDE_USAGE_ACCOUNT_1_COOKIE",
            api_url_env_key="CLAUDE_USAGE_ACCOUNT_1_API_URL",
        ),
        Account(
            key="2",
            label="Team Plan",
            cookie="session=team",
            api_url=URL_2,
            cookie_env_key="CLAUDE_USAGE_ACCOUNT_2_COOKIE",
            api_url_env_key="CLAUDE_USAGE_ACCOUNT_2_API_URL",
        ),
    ]


def test_load_accounts_skips_gaps_in_numbering(monkeypatch, tmp_path):
    """ACCOUNT_1 + ACCOUNT_3 uten ACCOUNT_2 skal gi to kontoer, ikke én."""
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n"
        f"CLAUDE_USAGE_ACCOUNT_3_LABEL=Max\n"
        f"CLAUDE_USAGE_ACCOUNT_3_COOKIE=session=max\n"
        f"CLAUDE_USAGE_ACCOUNT_3_API_URL={URL_2}\n",
    )

    accounts = config.load_accounts()

    assert [a.key for a in accounts] == ["1", "3"]
    assert [a.label for a in accounts] == ["Pro", "Max"]


def test_load_accounts_falls_back_to_generic_label(monkeypatch, tmp_path):
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_ACCOUNT_2_COOKIE=session=abc\n"
        f"CLAUDE_USAGE_ACCOUNT_2_API_URL={URL_1}\n",
    )

    accounts = config.load_accounts()

    assert [a.label for a in accounts] == ["Konto 2"]


def test_load_accounts_skips_entry_missing_cookie(monkeypatch, tmp_path):
    """En halvferdig oppføring skal hoppes over, ikke gi en konto uten cookie."""
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n"
        f"CLAUDE_USAGE_ACCOUNT_2_LABEL=Team Plan\n"
        f"CLAUDE_USAGE_ACCOUNT_2_API_URL={URL_2}\n",
    )

    accounts = config.load_accounts()

    assert [a.key for a in accounts] == ["1"]


# --- Bakoverkompatibilitet ------------------------------------------------


def test_load_accounts_accepts_legacy_unnumbered_keys(monkeypatch, tmp_path):
    """Eksisterende .env-filer med de gamle nøklene skal fortsatt virke."""
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_COOKIE=session=abc\nCLAUDE_USAGE_API_URL={URL_1}\n",
    )

    accounts = config.load_accounts()

    assert accounts == [
        Account(
            key="legacy",
            label="Konto 1",
            cookie="session=abc",
            api_url=URL_1,
            cookie_env_key="CLAUDE_USAGE_COOKIE",
            api_url_env_key="CLAUDE_USAGE_API_URL",
        )
    ]


def test_load_accounts_prefers_numbered_over_legacy(monkeypatch, tmp_path):
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_COOKIE=session=gammel\n"
        f"CLAUDE_USAGE_API_URL={URL_2}\n"
        f"CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=ny\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n",
    )

    accounts = config.load_accounts()

    assert [a.cookie for a in accounts] == ["session=ny"]


def test_load_accounts_raises_when_nothing_configured(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, "")

    with pytest.raises(config.CredentialsMissingError):
        config.load_accounts()


# --- Lesemåte: fil vs. shell ---------------------------------------------


def test_load_accounts_picks_up_updated_env_file_without_restart(monkeypatch, tmp_path):
    env_file = _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=old\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n",
    )

    assert config.load_accounts()[0].cookie == "session=old"

    env_file.write_text(
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=new\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n"
    )

    assert config.load_accounts()[0].cookie == "session=new"


def test_load_accounts_prefers_shell_env_over_env_file(monkeypatch, tmp_path):
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_ACCOUNT_1_COOKIE=session=from-file\n"
        f"CLAUDE_USAGE_ACCOUNT_1_API_URL={URL_1}\n",
    )
    monkeypatch.setenv("CLAUDE_USAGE_ACCOUNT_1_COOKIE", "session=from-shell")

    accounts = config.load_accounts()

    assert accounts[0].cookie == "session=from-shell"
    assert accounts[0].api_url == URL_1


def test_env_file_path_ignores_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = config.env_file_path()

    assert result.name == ".env"
    assert result.parent.name == "claude-usage"


# --- Aktiv konto ----------------------------------------------------------


def test_active_account_key_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "state_file_path", lambda: tmp_path / "state" / "state.json")

    assert config.load_active_account_key() is None

    config.save_active_account_key("2")

    assert config.load_active_account_key() == "2"


def test_load_active_account_key_survives_corrupt_state_file(monkeypatch, tmp_path):
    """Et ødelagt valg er en bagatell — appen skal ikke krasje på det."""
    state_file = tmp_path / "state.json"
    state_file.write_text("{ikke gyldig json")
    monkeypatch.setattr(config, "state_file_path", lambda: state_file)

    assert config.load_active_account_key() is None


def test_legacy_account_reports_the_env_keys_it_actually_uses(monkeypatch, tmp_path):
    """Hjelpeteksten må navngi nøklene som står i brukerens fil — en gammel
    .env har CLAUDE_USAGE_COOKIE, ikke CLAUDE_USAGE_ACCOUNT_1_COOKIE."""
    _env(
        monkeypatch,
        tmp_path,
        f"CLAUDE_USAGE_COOKIE=session=abc\nCLAUDE_USAGE_API_URL={URL_1}\n",
    )

    (account,) = config.load_accounts()

    assert account.cookie_env_key == "CLAUDE_USAGE_COOKIE"
    assert account.api_url_env_key == "CLAUDE_USAGE_API_URL"
