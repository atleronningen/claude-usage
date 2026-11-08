from unittest.mock import patch

import pytest

from claude_usage import accounts


@pytest.fixture(autouse=True)
def discover():
    """Stubb organisasjonsoppslaget, så tester av hentestien slipper nettet.

    Adressen inneholder cookien, slik at tester kan se hvilken konto et kall
    gjaldt. Hurtiglageret tømmes, så ingen test arver en annens adresse.
    """
    accounts._usage_urls.clear()
    with patch(
        "claude_usage.accounts.discover_usage_url",
        side_effect=lambda cookie: f"https://usage/{cookie}",
    ) as mock:
        yield mock
    accounts._usage_urls.clear()
