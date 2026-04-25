"""State machine for interactive embedding backend failover."""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass(slots=True)
class InteractiveBackendState:
    local_health_status: str = "unknown"
    effective_backend: str = "llama_server_local"
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_health_check_at: float = 0.0
    healthcheck_seconds: int = 15
    recovery_successes: int = 2
    failure_threshold: int = 1

    def should_probe_local(self, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return (current - self.last_health_check_at) >= self.healthcheck_seconds

    def mark_local_success(self, now: float | None = None) -> None:
        self.local_health_status = "healthy"
        self.effective_backend = "llama_server_local"
        self.consecutive_successes = min(self.consecutive_successes + 1, self.recovery_successes)
        self.consecutive_failures = 0
        self.last_health_check_at = time.time() if now is None else now

    def mark_local_failure(self, now: float | None = None) -> None:
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_health_check_at = time.time() if now is None else now
        if self.consecutive_failures >= self.failure_threshold:
            self.local_health_status = "unhealthy"
            self.effective_backend = "jina_api"

    def observe_recovery_probe(self, healthy: bool, now: float | None = None) -> None:
        current = time.time() if now is None else now
        self.last_health_check_at = current
        if healthy:
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            if self.consecutive_successes >= self.recovery_successes:
                self.local_health_status = "healthy"
                self.effective_backend = "llama_server_local"
        else:
            self.consecutive_successes = 0
            self.local_health_status = "unhealthy"
            self.effective_backend = "jina_api"
