"""Verify that a GSTIN is registered on the GST portal using the FastGST API.

Results are cached in Redis for 30 days to avoid repeated API calls.
Falls back to format-only validation if the API or Redis is unavailable.
"""

import re

import httpx
import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GSTIN_REGEX = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)

_CACHE_TTL = 2_592_000  # 30 days in seconds


def _is_valid_format(gstin: str) -> bool:
    return bool(GSTIN_REGEX.match(gstin.upper()))


async def verify_gstin_exists(gstin: str) -> bool:
    """Return True if GSTIN format is valid and portal lookup confirms it exists.

    Checks Redis cache first (30-day TTL). On cache miss calls the FastGST API.
    Falls back to True (format-only) if Redis or the API is unavailable so
    registration is never blocked by infrastructure issues.
    """
    gstin = gstin.upper().strip()

    if not _is_valid_format(gstin):
        return False

    cache_key = f"gstin_valid:{gstin}"

    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)

        cached = await r.get(cache_key)
        if cached is not None:
            await r.aclose()
            result: bool = cached.decode() == "1"
            return result

        valid = await _call_gstin_api(gstin)

        await r.setex(cache_key, _CACHE_TTL, "1" if valid else "0")
        await r.aclose()
        return valid

    except Exception as exc:
        logger.warning("gstin_validation_cache_error", gstin=gstin, error=str(exc))
        return True  # fail open — never block registration on infra errors


async def _call_gstin_api(gstin: str) -> bool:
    """Call FastGST API to verify GSTIN exists. Falls back to True on any error."""
    api_key = getattr(settings, "FASTGST_API_KEY", None)

    if not api_key:
        # No API key configured — accept any well-formed GSTIN
        return True

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"https://api.fastgst.in/v1/search/gstin/{gstin}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        if response.status_code == 200:
            data = response.json()
            api_result: bool = data.get("status") == "Active"
            return api_result
        if response.status_code == 404:
            return False
        # Any other status (rate limit, server error) — fail open
        logger.warning("gstin_api_non200", status=response.status_code, gstin=gstin)
        return True
    except Exception as exc:
        logger.warning("gstin_api_call_failed", gstin=gstin, error=str(exc))
        return True  # fail open on API errors
