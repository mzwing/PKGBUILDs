from __future__ import annotations

import hashlib
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tools.reporting import LOGGER

USER_AGENT = "PKGBUILDs-nvchecker-updater/1.0"
DEFAULT_TIMEOUT = 30.0
DEFAULT_ATTEMPTS = 3
_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

# A release index is asked for once per asset per architecture. Caching keeps a
# multi-arch package to a single API call instead of one per architecture.
_JSON_CACHE: dict[tuple[str, str], Any] = {}


def clear_cache() -> None:
    _JSON_CACHE.clear()


def fetch_bytes(
    url: str,
    *,
    user_agent: str = USER_AGENT,
    timeout: float = DEFAULT_TIMEOUT,
    attempts: int = DEFAULT_ATTEMPTS,
) -> bytes:
    return _with_retries(
        lambda: _open(url, user_agent, timeout).read(),
        url=url,
        attempts=attempts,
    )


def fetch_json(
    url: str,
    *,
    user_agent: str = USER_AGENT,
    timeout: float = DEFAULT_TIMEOUT,
    attempts: int = DEFAULT_ATTEMPTS,
) -> Any:
    key = (url, user_agent)
    if key not in _JSON_CACHE:
        payload = fetch_bytes(
            url, user_agent=user_agent, timeout=timeout, attempts=attempts
        )
        _JSON_CACHE[key] = json.loads(payload.decode("utf-8"))
    return _JSON_CACHE[key]


def sha256_url(
    url: str,
    *,
    user_agent: str = USER_AGENT,
    timeout: float = DEFAULT_TIMEOUT,
    attempts: int = DEFAULT_ATTEMPTS,
) -> str:
    def digest() -> str:
        hasher = hashlib.sha256()
        with _open(url, user_agent, timeout) as response:
            while chunk := response.read(1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()

    return _with_retries(digest, url=url, attempts=attempts)


def _open(url: str, user_agent: str, timeout: float):
    return urlopen(Request(url, headers={"User-Agent": user_agent}), timeout=timeout)


def _with_retries[T](operation, *, url: str, attempts: int) -> T:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (URLError, TimeoutError, ConnectionError) as error:
            if not _is_retryable(error) or attempt == attempts:
                raise
            last_error = error
            delay = 2.0 ** (attempt - 1)
            LOGGER.warning(
                "%s: attempt %d/%d failed (%s); retrying in %.0fs",
                url,
                attempt,
                attempts,
                error,
                delay,
            )
            time.sleep(delay)
    raise AssertionError(f"unreachable: {last_error}")


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, HTTPError):
        return error.code in _RETRY_STATUSES
    return True
