"""简单的进程内限频：滑动窗口计数，只适用于单个 API 进程；多进程部署时需改用 Redis 等共享存储"""

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float = 60) -> None:
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> bool:
        """记录一次请求；窗口内请求数已达上限时返回 False，且不计入本次"""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


order_create_limiter = SlidingWindowLimiter(window_seconds=60)
