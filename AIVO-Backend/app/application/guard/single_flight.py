"""SingleFlight 本地并发控制服务"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class FlightEntry:
    future: "asyncio.Future[Any]"
    expire_at: float


class InterviewAiSingleFlightService:
    """本地 SingleFlight 服务，避免同 key 的并发请求重复调用底层能力"""

    def __init__(
        self,
        enable: bool = True,
        ttl: float = 4.0,
        wait_timeout: float = 5.0,
        cleanup_threshold: int = 256,
    ):
        self._enable = enable
        self._ttl = ttl
        self._wait_timeout = wait_timeout
        self._cleanup_threshold = cleanup_threshold
        self._flights: Dict[str, FlightEntry] = {}
        self._lock = asyncio.Lock()

    async def execute(self, key: str, func: Callable[[], Awaitable[T]]) -> T:
        if not self._enable or not key:
            return await func()

        now = time.monotonic()

        async with self._lock:
            entry = self._flights.get(key)
            if entry is None or entry.expire_at <= now:
                future: "asyncio.Future[Any]" = asyncio.Future()
                entry = FlightEntry(future=future, expire_at=now + self._ttl)
                self._flights[key] = entry
                is_leader = True
            else:
                is_leader = False

        if is_leader:
            try:
                result = await func()
                entry.future.set_result(result)
                return result
            except Exception as exc:
                entry.future.set_exception(exc)
                self._flights.pop(key, None)
                raise
            finally:
                self._cleanup_expired()
        else:
            try:
                return await asyncio.wait_for(entry.future, timeout=self._wait_timeout)
            except asyncio.TimeoutError:
                self._flights.pop(key, None)
                raise
            except Exception:
                raise

    def _cleanup_expired(self) -> None:
        if len(self._flights) < self._cleanup_threshold:
            return
        now = time.monotonic()
        expired = [key for key, entry in self._flights.items() if entry.expire_at <= now]
        for key in expired:
            self._flights.pop(key, None)


interview_ai_single_flight = InterviewAiSingleFlightService()
