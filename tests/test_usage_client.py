from unittest.mock import MagicMock, patch

import pytest

from claude_usage.usage_client import (
    UsageAuthError,
    UsageData,
    UsageFetchError,
    fetch_usage,
)

API_URL = "https://claude.ai/api/organizations/test-org/usage"


def _sample_response(five_hour_utilization=62.0, seven_day_utilization=58.0):
    return {
        "five_hour": {
            "utilization": five_hour_utilization,
            "resets_at": "2026-07-24T21:09:59.018485+00:00",
        },
        "seven_day": {
            "utilization": seven_day_utilization,
            "resets_at": "2026-07-28T19:59:59.018510+00:00",
        },
    }


def _mock_response(status_code, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    if status_code >= 400:
        from curl_cffi.requests.exceptions import HTTPError

        mock_resp.raise_for_status.side_effect = HTTPError(f"{status_code} error")
    else:
        mock_resp.raise_for_status.side_effect = None
    return mock_resp


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_parses_percentages(mock_get):
    mock_get.return_value = _mock_response(200, _sample_response())

    usage = fetch_usage(cookie="session=abc", api_url=API_URL)

    assert usage == UsageData(session_percent=62, weekly_percent=58)
    mock_get.assert_called_once_with(
        API_URL, headers={"Cookie": "session=abc"}, impersonate="chrome", timeout=10
    )


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_rounds_float_percentages(mock_get):
    mock_get.return_value = _mock_response(
        200, _sample_response(five_hour_utilization=61.6, seven_day_utilization=58.4)
    )

    usage = fetch_usage(cookie="session=abc", api_url=API_URL)

    assert usage == UsageData(session_percent=62, weekly_percent=58)


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_raises_auth_error_on_401(mock_get):
    mock_get.return_value = _mock_response(401)

    with pytest.raises(UsageAuthError):
        fetch_usage(cookie="session=expired", api_url=API_URL)


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_raises_auth_error_on_403(mock_get):
    mock_get.return_value = _mock_response(403)

    with pytest.raises(UsageAuthError):
        fetch_usage(cookie="session=expired", api_url=API_URL)


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_raises_fetch_error_on_server_error(mock_get):
    mock_get.return_value = _mock_response(500)

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_raises_fetch_error_on_unexpected_shape(mock_get):
    mock_get.return_value = _mock_response(200, {"unexpected": "shape"})

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)


@patch("claude_usage.usage_client.requests.get")
def test_fetch_usage_raises_fetch_error_on_network_error(mock_get):
    from curl_cffi.requests.exceptions import RequestException

    mock_get.side_effect = RequestException("connection failed")

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)
