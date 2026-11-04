import time
import logging
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

def get_client_ip(request):
    """Safely extracts client IP address considering proxy headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip


def check_rate_limit(key, limit=5, window=60):
    """
    Sliding window rate-limiter using Django cache.
    :param key: Cache key identifier (e.g. 'ratelimit:login:1.2.3.4')
    :param limit: Maximum allowed attempts in window
    :param window: Window duration in seconds
    :return: (allowed: bool, remaining: int, retry_after: int)
    """
    now = int(time.time())
    try:
        timestamps = cache.get(key, [])
        if not isinstance(timestamps, list):
            timestamps = []
            
        # Keep only timestamps within the rolling window
        valid_timestamps = [ts for ts in timestamps if now - ts < window]
        
        if len(valid_timestamps) >= limit:
            oldest = valid_timestamps[0]
            retry_after = max(1, window - (now - oldest))
            return False, 0, retry_after

        valid_timestamps.append(now)
        cache.set(key, valid_timestamps, timeout=window)
        return True, limit - len(valid_timestamps), 0
    except Exception as e:
        logger.warning(f"Rate limit cache check error: {e}")
        # Fail open securely if cache has an issue so legitimate traffic isn't blocked
        return True, limit, 0

