import json
import logging
import functools
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


def rate_limit(key_prefix, limit=10, period=60, methods=('POST',), only_when_field=None):
    """
    Zero-dependency cache-backed rate-limiting decorator.
    :param key_prefix: Cache key namespace (e.g., 'auth_login', 'ai_task_create')
    :param limit: Maximum allowed requests within the period
    :param period: Rolling time window in seconds
    :param methods: Tuple of HTTP methods subject to rate-limiting
    :param only_when_field: Field name; if specified, only rate-limit if present & non-empty
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if request.method not in methods:
                return view_func(request, *args, **kwargs)

            # Determine field filtering if only_when_field is set or key is AI-related
            target_field = only_when_field
            if target_field is None and key_prefix == 'ai_task_create':
                target_field = 'natural_language'

            if target_field:
                field_names = [target_field]
                if target_field in ('natural_language', 'smart_prompt'):
                    field_names = ['natural_language', 'smart_prompt']

                field_present = any(request.POST.get(f) for f in field_names)
                if not field_present and request.content_type == 'application/json' and request.body:
                    try:
                        body_data = json.loads(request.body)
                        if isinstance(body_data, dict):
                            field_present = any(body_data.get(f) for f in field_names)
                    except Exception:
                        pass

                if not field_present:
                    return view_func(request, *args, **kwargs)

            # Identify user (authenticated user id or anonymous client IP)
            if getattr(request, 'user', None) and request.user.is_authenticated:
                identifier = f"user_{request.user.id}"
            else:
                identifier = get_client_ip(request)

            cache_key = f"rl:{key_prefix}:{identifier}"

            try:
                current_count = cache.get(cache_key)
                if current_count is not None and current_count >= limit:
                    is_ajax = (
                        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
                        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                        request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or
                        'application/json' in request.headers.get('accept', '') or
                        'application/json' in request.headers.get('Accept', '') or
                        request.content_type == 'application/json'
                    )
                    if is_ajax:
                        resp = JsonResponse(
                            {'error': "You're moving fast! Please wait a moment before trying again."},
                            status=429
                        )
                    else:
                        resp = HttpResponse(
                            "You're moving fast! Please wait a moment before trying again.",
                            status=429
                        )
                    resp['Retry-After'] = str(period)
                    return resp

                if current_count is None:
                    cache.set(cache_key, 1, timeout=period)
                else:
                    try:
                        cache.incr(cache_key)
                    except Exception:
                        cache.set(cache_key, current_count + 1, timeout=period)

            except Exception as e:
                logger.warning(f"Rate limit cache operation error: {e}")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def check_rate_limit(key, limit=5, window=60):
    """
    Backwards-compatible helper for manual rate limit checking.
    """
    try:
        count = cache.get(key)
        if count is not None and count >= limit:
            return False, 0, window
        if count is None:
            cache.set(key, 1, timeout=window)
        else:
            try:
                cache.incr(key)
            except Exception:
                cache.set(key, count + 1, timeout=window)
        return True, limit - (count or 1), 0
    except Exception as e:
        logger.warning(f"check_rate_limit error: {e}")
        return True, limit, 0
