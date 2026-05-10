"""
Circuit Breaker pattern for external API calls.
Provides fault tolerance and prevents cascading failures.
"""
import asyncio
import logging
import time
from enum import Enum
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker implementation with configurable thresholds.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
        excluded_exceptions: tuple = (),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.excluded_exceptions = excluded_exceptions
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def failure_count(self) -> int:
        return self._failure_count
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. Call rejected."
                    )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._on_success()
            return result
        except self.excluded_exceptions:
            await self._on_success()
            raise
        except Exception as e:
            await self._on_failure()
            raise
    
    def _should_attempt_recovery(self) -> bool:
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.recovery_timeout
    
    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(f"Circuit breaker '{self.name}' recovered - CLOSING")
                    self._reset()
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit breaker '{self.name}' failed recovery - OPENING")
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker '{self.name}' opened after {self._failure_count} failures"
                )
                self._state = CircuitState.OPEN
    
    def _reset(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
    
    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and rejecting calls."""
    pass


# Global circuit breakers for different services
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> CircuitBreaker:
    """Get or create a named circuit breaker."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _circuit_breakers[name]


def get_all_circuit_breakers_status() -> dict:
    """Get status of all circuit breakers."""
    return {name: cb.get_status() for name, cb in _circuit_breakers.items()}


# Decorator for easy circuit breaker usage
def circuit_breaker(name: str, excluded_exceptions: tuple = ()):
    """Decorator to wrap functions with circuit breaker."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cb = get_circuit_breaker(name)
            return await cb.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            cb = get_circuit_breaker(name)
            return asyncio.run(cb.call(func, *args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator