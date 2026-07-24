from unittest.mock import patch

from claude_usage import __version__
from claude_usage.config import CredentialsMissingError
from claude_usage.main import ClaudeUsageApp


def test_menu_shows_version():
    with patch(
        "claude_usage.main.config.load_credentials",
        side_effect=CredentialsMissingError("mangler"),
    ):
        app = ClaudeUsageApp()

    assert app.version_item.title == f"v{__version__}"
