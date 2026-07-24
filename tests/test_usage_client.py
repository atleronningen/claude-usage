import pytest
import responses

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


@responses.activate
def test_fetch_usage_parses_percentages():
    responses.add(responses.GET, API_URL, json=_sample_response(), status=200)

    usage = fetch_usage(cookie="session=abc", api_url=API_URL)

    assert usage == UsageData(session_percent=62, weekly_percent=58)


@responses.activate
def test_fetch_usage_rounds_float_percentages():
    responses.add(
        responses.GET,
        API_URL,
        json=_sample_response(five_hour_utilization=61.6, seven_day_utilization=58.4),
        status=200,
    )

    usage = fetch_usage(cookie="session=abc", api_url=API_URL)

    assert usage == UsageData(session_percent=62, weekly_percent=58)


@responses.activate
def test_fetch_usage_raises_auth_error_on_401():
    responses.add(responses.GET, API_URL, json={}, status=401)

    with pytest.raises(UsageAuthError):
        fetch_usage(cookie="session=expired", api_url=API_URL)


@responses.activate
def test_fetch_usage_raises_auth_error_on_403():
    responses.add(responses.GET, API_URL, json={}, status=403)

    with pytest.raises(UsageAuthError):
        fetch_usage(cookie="session=expired", api_url=API_URL)


@responses.activate
def test_fetch_usage_raises_fetch_error_on_server_error():
    responses.add(responses.GET, API_URL, json={}, status=500)

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)


@responses.activate
def test_fetch_usage_raises_fetch_error_on_unexpected_shape():
    responses.add(responses.GET, API_URL, json={"unexpected": "shape"}, status=200)

    with pytest.raises(UsageFetchError):
        fetch_usage(cookie="session=abc", api_url=API_URL)
