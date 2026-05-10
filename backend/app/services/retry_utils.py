"""
Retry utilities for background tasks with exponential backoff.
"""
import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Any, Optional, Type, Tuple

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


def async_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for async functions with exponential backoff retry.
    
    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Multiplier for delay after each retry
        retriable_exceptions: Tuple of exceptions that trigger retry
        on_retry: Callback function called on each retry (exception, attempt, delay)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Retry exhausted for {func.__name__} after {max_attempts} attempts. "
                            f"Last error: {e}"
                        )
                        raise RetryError(
                            f"Failed after {max_attempts} attempts: {e}"
                        ) from e
                    
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt, delay)
                    
                    await asyncio.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for sync functions with exponential backoff retry.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retriable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Retry exhausted for {func.__name__} after {max_attempts} attempts. "
                            f"Last error: {e}"
                        )
                        raise RetryError(
                            f"Failed after {max_attempts} attempts: {e}"
                        ) from e
                    
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt, delay)
                    
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class TaskRetryConfig:
    """Configuration for task retries."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 2.0,
        max_delay: float = 120.0,
        backoff_factor: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
    
    def create_decorator(self, retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,)):
        return async_retry(
            max_attempts=self.max_attempts,
            initial_delay=self.initial_delay,
            max_delay=self.max_delay,
            backoff_factor=self.backoff_factor,
            retriable_exceptions=retriable_exceptions,
        )


# Predefined retry configs for different task types
DATA_FETCH_RETRY_CONFIG = TaskRetryConfig(
    max_attempts=3,
    initial_delay=5.0,
    max_delay=60.0,
    backoff_factor=2.0,
)

SIGNAL_GENERATION_RETRY_CONFIG = TaskRetryConfig(
    max_attempts=2,
    initial_delay=10.0,
    max_delay=120.0,
    backoff_factor=2.0,
)

PAPER_TRADING_RETRY_CONFIG = TaskRetryConfig(
    max_attempts=3,
    initial_delay=2.0,
    max_delay=30.0,
    backoff_factor=1.5,
)