"""The app clock: what time it is "now" in the simulated year.

No background thread. The clock remembers an anchor (sim time + real time when it last changed);
while playing, now = anchor + real seconds elapsed × speed (sim hours per real second).
It wraps from the end of the data year back to the start. "Now" is always a whole hour.
"""

import threading
import time

import pandas as pd

from app.data import campus
from app.data.campus import DataError

DEFAULT_TIME = "2025-12-10T12:00"  # a winter term Wednesday at lunch: heating on, MED-A busy
DEFAULT_SPEED = 1.0  # sim hours per real second while playing
MAX_SPEED = 24 * 7  # a week per second


class Clock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bounds: tuple[pd.Timestamp, pd.Timestamp] | None = None
        self._anchor_sim = pd.Timestamp(DEFAULT_TIME)
        self._anchor_real = time.time()
        self._speed = DEFAULT_SPEED
        self._playing = False

    def _range(self) -> tuple[pd.Timestamp, pd.Timestamp]:
        if self._bounds is None:
            r = campus.time_range()
            self._bounds = (pd.Timestamp(r["start"]), pd.Timestamp(r["end"]))
        return self._bounds

    def _wrap(self, t: pd.Timestamp) -> pd.Timestamp:
        start, end = self._range()
        span = end - start + pd.Timedelta(hours=1)
        return start + (t - start) % span

    def _exact(self) -> pd.Timestamp:
        if not self._playing:
            return self._anchor_sim
        return self._wrap(self._anchor_sim + pd.Timedelta(hours=(time.time() - self._anchor_real) * self._speed))

    def _reanchor(self) -> None:
        self._anchor_sim, self._anchor_real = self._exact(), time.time()

    def now(self) -> pd.Timestamp:
        """Current sim time, floored to the hour."""
        with self._lock:
            return self._exact().floor("h")

    def state(self) -> dict:
        """Everything the screen needs to show and animate the clock without asking every second:
        sim_time = anchor.sim_time + (now_epoch − anchor.real_epoch) × speed_hours_per_second (if playing)."""
        with self._lock:
            start, end = self._range()
            return {
                "sim_time": self._exact().floor("h").strftime("%Y-%m-%dT%H:%M"),
                "playing": self._playing,
                "speed_hours_per_second": self._speed,
                "anchor": {"sim_time": self._exact().strftime("%Y-%m-%dT%H:%M:%S"), "real_epoch": time.time()},
                "range": {"start": start.strftime("%Y-%m-%dT%H:%M"), "end": end.strftime("%Y-%m-%dT%H:%M")},
            }

    def set_time(self, t) -> dict:
        try:
            ts = pd.Timestamp(t)
        except (ValueError, TypeError) as e:
            raise DataError(f"Can't read {t!r} as a time. Use e.g. '2026-01-15T14:00'.") from e
        start, end = self._range()
        if not start <= ts <= end:
            raise DataError(f"{ts} is outside the data year ({start} to {end}).")
        with self._lock:
            self._anchor_sim, self._anchor_real = ts.floor("h"), time.time()
        return self.state()

    def play(self, speed: float | None = None) -> dict:
        if speed is not None and not 0 < speed <= MAX_SPEED:
            raise DataError(f"Speed must be between 0 and {MAX_SPEED} sim hours per second.")
        with self._lock:
            self._reanchor()
            self._speed = self._speed if speed is None else float(speed)
            self._playing = True
        return self.state()

    def set_speed(self, speed: float) -> dict:
        """Change the speed without starting or stopping the clock."""
        if not 0 < speed <= MAX_SPEED:
            raise DataError(f"Speed must be between 0 and {MAX_SPEED} sim hours per second.")
        with self._lock:
            self._reanchor()
            self._speed = float(speed)
        return self.state()

    def pause(self) -> dict:
        with self._lock:
            self._reanchor()
            self._anchor_sim = self._anchor_sim.floor("h")
            self._playing = False
        return self.state()


CLOCK = Clock()
