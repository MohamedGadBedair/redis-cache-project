import logging
import time
from enum import Enum

logger = logging.getLogger(__name__)


class State(str, Enum):
    CLOSED = "closed"        # طبيعي
    OPEN = "open"            # Redis واقع: ما نكلمهوش
    HALF_OPEN = "half_open"  # probe واحد شغال


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_timeout: float):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at: float | None = None
        self._probe_started_at: float | None = None

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None

    @property
    def state(self) -> State:
        if self._opened_at is None:
            return State.CLOSED
        if self._probe_started_at is not None:
            return State.HALF_OPEN
        return State.OPEN

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        now = time.monotonic()
        # مفتوحة: نسمح بمحاولة واحدة بس كل reset_timeout
        waited = now - (self._probe_started_at or self._opened_at)
        if waited >= self.reset_timeout:
            self._probe_started_at = now
            return True
        return False

    def record_success(self) -> None:
        if self._opened_at is not None:
            logger.warning("Redis circuit CLOSED (recovered)")
        self._failures = 0
        self._opened_at = None
        self._probe_started_at = None

    def record_failure(self) -> None:
        self._failures += 1
        self._probe_started_at = None
        if self._failures >= self.failure_threshold:
            if self._opened_at is None:
                logger.error("Redis circuit OPEN after %d failures", self._failures)
            self._opened_at = time.monotonic()


from app.config import settings  # noqa: E402

breaker = CircuitBreaker(
    settings.breaker_failure_threshold,
    settings.breaker_reset_seconds,
)