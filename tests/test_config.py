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
        "CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-pro\n"
        "CLAUDE_USAGE_ACCOUNT_2_LABEL=Team Plan\n"
        "CLAUDE_USAGE_ACCOUNT_2_SESSION_KEY=sk-ant-team\n",
    )

    accounts = config.load_accounts()

    assert accounts == [
        Account(
            key="1",
            label="Pro",
            cookie="sessionKey=sk-ant-pro",
            session_key_env_key="CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY",
        ),
        Account(
            key="2",
            label="Team Plan",
            cookie="sessionKey=sk-ant-team",
            session_key_env_key="CLAUDE_USAGE_ACCOUNT_2_SESSION_KEY",
        ),
    ]


def test_load_accounts_tolerates_pasted_cookie_name(monkeypatch, tmp_path):
    """Limer brukeren inn «sessionKey=sk-ant-…», skal navnet ikke dobles."""
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY= sessionKey=sk-ant-pro \n",
    )

    (account,) = config.load_accounts()

    assert account.cookie == "sessionKey=sk-ant-pro"


def test_load_accounts_skips_gaps_in_numbering(monkeypatch, tmp_path):
    """ACCOUNT_1 + ACCOUNT_3 uten ACCOUNT_2 skal gi to kontoer, ikke én."""
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-pro\n"
        "CLAUDE_USAGE_ACCOUNT_3_LABEL=Max\n"
        "CLAUDE_USAGE_ACCOUNT_3_SESSION_KEY=sk-ant-max\n",
    )

    accounts = config.load_accounts()

    assert [a.key for a in accounts] == ["1", "3"]
    assert [a.label for a in accounts] == ["Pro", "Max"]


def test_load_accounts_falls_back_to_generic_label(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, "CLAUDE_USAGE_ACCOUNT_2_SESSION_KEY=sk-ant-abc\n")

    accounts = config.load_accounts()

    assert [a.label for a in accounts] == ["Konto 2"]


def test_load_accounts_skips_entry_missing_session_key(monkeypatch, tmp_path):
    """En halvferdig oppføring skal hoppes over, ikke gi en konto uten innlogging."""
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-pro\n"
        "CLAUDE_USAGE_ACCOUNT_2_LABEL=Team Plan\n"
        f"CLAUDE_USAGE_ACCOUNT_2_API_URL={URL_2}\n",
    )

    accounts = config.load_accounts()

    assert [a.key for a in accounts] == ["1"]


# --- Bakoverkompatibilitet ------------------------------------------------


def test_load_accounts_accepts_full_cookie_header(monkeypatch, tmp_path):
    """Gamle blokker med hel Cookie-header virker – sessionKey står inni den.
    `_API_URL` ignoreres, så en feil adresse der ikke lenger kan ødelegge."""
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_COOKIE=a=1; sessionKey=sk-ant-pro\n"
        "CLAUDE_USAGE_ACCOUNT_1_API_URL=https://claude.ai/feil/user_settings\n",
    )

    (account,) = config.load_accounts()

    assert account.cookie == "a=1; sessionKey=sk-ant-pro"
    assert account.session_key_env_key == "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY"


def test_load_accounts_prefers_session_key_over_cookie(monkeypatch, tmp_path):
    """Den nye sessionKey-en brukeren limer inn skal vinne over en gammel
    Cookie-header som fortsatt står i blokken."""
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_COOKIE=sessionKey=sk-ant-gammel\n"
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-ny\n",
    )

    (account,) = config.load_accounts()

    assert account.cookie == "sessionKey=sk-ant-ny"


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
            session_key_env_key="CLAUDE_USAGE_SESSION_KEY",
        )
    ]


def test_load_accounts_accepts_legacy_unnumbered_session_key(monkeypatch, tmp_path):
    """Følger brukeren hjelpeteksten på et gammelt oppsett, havner sessionKey
    i CLAUDE_USAGE_SESSION_KEY – den skal vinne over den gamle cookien."""
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_COOKIE=sessionKey=sk-ant-gammel\n"
        "CLAUDE_USAGE_SESSION_KEY=sk-ant-ny\n",
    )

    (account,) = config.load_accounts()

    assert account.cookie == "sessionKey=sk-ant-ny"


def test_load_accounts_prefers_numbered_over_legacy(monkeypatch, tmp_path):
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_COOKIE=session=gammel\n"
        "CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-ny\n",
    )

    accounts = config.load_accounts()

    assert [a.cookie for a in accounts] == ["sessionKey=sk-ant-ny"]


def test_load_accounts_raises_when_nothing_configured(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path, "")

    with pytest.raises(config.CredentialsMissingError):
        config.load_accounts()


# --- Lesemåte: fil vs. shell ---------------------------------------------


def test_load_accounts_picks_up_updated_env_file_without_restart(monkeypatch, tmp_path):
    env_file = _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-old\n",
    )

    assert config.load_accounts()[0].cookie == "sessionKey=sk-ant-old"

    env_file.write_text("CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-new\n")

    assert config.load_accounts()[0].cookie == "sessionKey=sk-ant-new"


def test_load_accounts_prefers_shell_env_over_env_file(monkeypatch, tmp_path):
    _env(
        monkeypatch,
        tmp_path,
        "CLAUDE_USAGE_ACCOUNT_1_LABEL=Pro\n"
        "CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY=sk-ant-from-file\n",
    )
    monkeypatch.setenv("CLAUDE_USAGE_ACCOUNT_1_SESSION_KEY", "sk-ant-from-shell")

    accounts = config.load_accounts()

    assert accounts[0].cookie == "sessionKey=sk-ant-from-shell"
    assert accounts[0].label == "Pro"


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


def test_legacy_account_names_the_unnumbered_session_key(monkeypatch, tmp_path):
    """Hjelpeteksten må navngi en nøkkel som passer brukerens fil – en gammel
    unummerert .env skal få CLAUDE_USAGE_SESSION_KEY, ikke ACCOUNT_1."""
    _env(monkeypatch, tmp_path, "CLAUDE_USAGE_COOKIE=session=abc\n")

    (account,) = config.load_accounts()

    assert account.session_key_env_key == "CLAUDE_USAGE_SESSION_KEY"
