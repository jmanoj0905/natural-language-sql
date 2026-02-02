"""Rate limiting middleware using slowapi."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def get_rate_limiter() -> Limiter:
    """
    Create and configure rate limiter.

    Returns:
        Configured Limiter instance
    """
    settings = get_settings()

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{settings.API_RATE_LIMIT_PER_MINUTE}/minute"],
        storage_uri="memory://",  # Use in-memory storage (can switch to Redis)
        strategy="fixed-window",  # Fixed time window strategy
        enabled=True
    )

    return limiter


# Create global limiter instance
limiter = get_rate_limiter()
