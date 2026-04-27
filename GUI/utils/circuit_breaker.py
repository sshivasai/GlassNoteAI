"""
utils/circuit_breaker.py — Circuit breaker pattern for connection pools.

Prevents cascading failures by temporarily stopping requests to failing services.

Usage:
    from utils.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(failure_threshold=5, timeout=60)

    if breaker.can_execute():
        try:
            response = api_call()
            breaker.record_success()
        except Exception as e:
            breaker.record_failure()
            raise
"""

import time
import threading
from enum import Enum
from typing import Callable, Optional
from dataclasses import dataclass
from utils.logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5         # Failures before opening
    success_threshold: int = 2         # Successes to close from half-open
    timeout: float = 60.0              # Seconds before trying half-open
    half_open_max_calls: int = 3       # Max calls in half-open state


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    States:
      - CLOSED: Normal operation, calls go through
      - OPEN: Service is failing, reject all calls
      - HALF_OPEN: Testing if service recovered

    Transitions:
      CLOSED → OPEN: After failure_threshold failures
      OPEN → HALF_OPEN: After timeout seconds
      HALF_OPEN → CLOSED: After success_threshold successes
      HALF_OPEN → OPEN: On any failure
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            half_open_max_calls=half_open_max_calls,
        )

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """
        Check if a call can be executed.

        Returns:
            bool: True if call should proceed
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._should_attempt_reset():
                    logger.info(f"[circuit:{self.name}] Transitioning to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

        return False

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.debug(f"[circuit:{self.name}] Success in HALF_OPEN ({self._success_count}/{self.config.success_threshold})")

                if self._success_count >= self.config.success_threshold:
                    logger.info(f"[circuit:{self.name}] Service recovered, closing circuit")
                    self._reset()

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        with self._lock:
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"[circuit:{self.name}] Failure in HALF_OPEN, reopening circuit")
                self._state = CircuitState.OPEN
                self._success_count = 0
                return

            if self._state == CircuitState.CLOSED:
                self._failure_count += 1
                logger.debug(f"[circuit:{self.name}] Failure recorded ({self._failure_count}/{self.config.failure_threshold})")

                if self._failure_count >= self.config.failure_threshold:
                    logger.warning(f"[circuit:{self.name}] Failure threshold reached, opening circuit")
                    self._state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._last_failure_time is None:
            return True

        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout

    def _reset(self):
        """Reset circuit to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def reset_manually(self):
        """Manually reset the circuit to closed."""
        with self._lock:
            logger.info(f"[circuit:{self.name}] Manual reset")
            self._reset()

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": self._last_failure_time,
            }


# ── Decorator ──────────────────────────────────────────────────────────────────

def with_circuit_breaker(breaker: CircuitBreaker):
    """
    Decorator to protect a function with a circuit breaker.

    Usage:
        breaker = CircuitBreaker(name="api-calls")

        @with_circuit_breaker(breaker)
        def api_call():
            return requests.get("https://api.example.com")
    """
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            if not breaker.can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{breaker.name}' is open"
                )

            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise

        return wrapper
    return decorator


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# ── Connection Pool Health Check ───────────────────────────────────────────────

class HealthChecker:
    """
    Periodic health checker for connection pools.

    Runs health checks in background and trips circuit breakers on failure.
    """

    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self._checks = {}
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def register_check(
        self,
        name: str,
        check_func: Callable[[], bool],
        breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Register a health check.

        Args:
            name: Check name
            check_func: Function that returns True if healthy
            breaker: Optional circuit breaker to control
        """
        with self._lock:
            self._checks[name] = {
                "func": check_func,
                "breaker": breaker,
            }

        logger.info(f"Health check registered: {name}")

    def start_monitoring(self):
        """Start health check monitoring."""
        if self._monitoring:
            return

        self._monitoring = True

        def _monitor():
            while self._monitoring:
                with self._lock:
                    checks = list(self._checks.items())

                for name, check_data in checks:
                    try:
                        is_healthy = check_data["func"]()

                        if not is_healthy:
                            logger.warning(f"Health check failed: {name}")
                            if check_data["breaker"]:
                                check_data["breaker"].record_failure()
                        else:
                            if check_data["breaker"]:
                                check_data["breaker"].record_success()

                    except Exception as e:
                        logger.error(f"Health check error for {name}: {e}", exc_info=True)
                        if check_data["breaker"]:
                            check_data["breaker"].record_failure()

                # Sleep in small chunks
                for _ in range(int(self.check_interval * 2)):
                    if not self._monitoring:
                        break
                    time.sleep(0.5)

        self._thread = threading.Thread(
            target=_monitor,
            daemon=True,
            name="health-checker"
        )
        self._thread.start()
        logger.info("Health monitoring started")

    def stop_monitoring(self):
        """Stop health check monitoring."""
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Health monitoring stopped")


# Global health checker instance
health_checker = HealthChecker()
