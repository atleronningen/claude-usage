from unittest.mock import patch

from claude_usage.notifier import ThresholdNotifier


def test_notifies_once_when_crossing_threshold():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=85, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 0

        notifier.check(session_percent=92, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1

        notifier.check(session_percent=93, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1  # ikke varslet på nytt


def test_notifies_again_after_percent_drops_and_rises_again():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=92, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1

        notifier.check(session_percent=10, weekly_percent=50, enabled=True)  # ny periode
        notifier.check(session_percent=91, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 2


def test_does_not_notify_when_disabled():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=95, weekly_percent=95, enabled=False)
        assert mock_notify.call_count == 0


def test_tracks_session_and_weekly_independently():
    notifier = ThresholdNotifier()
    with patch("claude_usage.notifier.rumps.notification") as mock_notify:
        notifier.check(session_percent=92, weekly_percent=50, enabled=True)
        assert mock_notify.call_count == 1

        notifier.check(session_percent=92, weekly_percent=91, enabled=True)
        assert mock_notify.call_count == 2
