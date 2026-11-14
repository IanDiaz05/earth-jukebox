"""Centralized API rate limit configuration.

The API is stateless and has no user authentication, so the client's IP
address is used as the rate-limit identity. A strict default limit is applied
because the ML engine (TensorFlow/OpenCV) uses significant resources per
request.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.DEFAULT_RATE_LIMIT],
)
