import rumps

THRESHOLD_PERCENT = 90


class ThresholdNotifier:
    def __init__(self):
        self._session_notified = False
        self._weekly_notified = False

    def check(self, session_percent: int, weekly_percent: int, enabled: bool) -> None:
        if not enabled:
            return
        self._session_notified = self._check_one(
            percent=session_percent,
            already_notified=self._session_notified,
            message=f"Session-grensen er nå {session_percent}% brukt",
        )
        self._weekly_notified = self._check_one(
            percent=weekly_percent,
            already_notified=self._weekly_notified,
            message=f"Ukentlig grense er nå {weekly_percent}% brukt",
        )

    def _check_one(self, percent: int, already_notified: bool, message: str) -> bool:
        if percent < THRESHOLD_PERCENT:
            return False
        if already_notified:
            return True
        rumps.notification(title="Claude Usage", subtitle="", message=message)
        return True
