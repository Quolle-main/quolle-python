"""HTTP client for the Quolle API."""

from __future__ import annotations

import json as _json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .errors import QuolleError
from .resources.emails import Emails  # noqa: F401  (re-exported via self.emails)
from .resources.webhooks import Webhooks

DEFAULT_BASE_URL = "https://api.quolle.com"
DEFAULT_TIMEOUT = 30.0
__version__ = "1.0.0"


class Quolle:
    """The Quolle API client.

    Args:
        api_key: Your Quolle API key (starts with ``qle_``). Falls back to the
            ``QUOLLE_API_KEY`` environment variable if not provided.
        base_url: API base URL. Defaults to ``https://api.quolle.com``.
        timeout: Per-request timeout in seconds. Defaults to 30.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
    ) -> None:
        import os

        key = api_key or os.environ.get("QUOLLE_API_KEY")
        if not key:
            raise ValueError(
                "A Quolle API key is required. Pass api_key= or set QUOLLE_API_KEY."
            )
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        #: Email operations (send, send_batch, get, cancel).
        self.emails = Emails(self)
        #: Webhook signature verification.
        self.webhooks = Webhooks()

    # -- Internal request helper ------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform an authenticated request and return the decoded JSON body.

        Transient failures (HTTP 429 and 5xx, plus network errors) are retried
        with exponential backoff, honoring the ``Retry-After`` header on 429.
        To avoid double-sending, a POST is only retried on a 5xx/network error
        when an ``Idempotency-Key`` is present; a 429 (rate limited, so the
        request was never processed) is always safe to retry.

        Raises:
            QuolleError: on a non-2xx response or transport failure after retries.
        """
        import time as _time

        url = f"{self.base_url}{path}"
        data = _json.dumps(body).encode("utf-8") if body is not None else None

        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"quolle-python/{__version__}",
        }
        if headers:
            req_headers.update(headers)

        idempotent_method = method.upper() in ("GET", "DELETE")
        has_idem = any(k.lower() == "idempotency-key" for k in req_headers)

        def safe_to_retry(status: Optional[int]) -> bool:
            if status == 429:
                return True  # not processed — always safe
            transient = status is None or 500 <= status <= 504
            return transient and (idempotent_method or has_idem)

        last_error: Optional[QuolleError] = None
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return _json.loads(raw) if raw else {}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8") if exc.fp else ""
                payload: Dict[str, Any] = {}
                try:
                    payload = _json.loads(raw) if raw else {}
                except ValueError:
                    payload = {}
                message = payload.pop("error", None) or exc.reason or "Request failed"
                last_error = QuolleError(message, status_code=exc.code, data=payload)
                if attempt < self.max_retries and safe_to_retry(exc.code):
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    _time.sleep(self._backoff(attempt, retry_after))
                    continue
                raise last_error from None
            except (urllib.error.URLError, TimeoutError) as exc:
                reason = getattr(exc, "reason", exc)
                last_error = QuolleError(f"Network error: {reason}")
                if attempt < self.max_retries and safe_to_retry(None):
                    _time.sleep(self._backoff(attempt, None))
                    continue
                raise last_error from None
        raise last_error or QuolleError("Request failed")

    def _backoff(self, attempt: int, retry_after: Optional[str]) -> float:
        """Seconds to wait before the next attempt: Retry-After if given, else
        exponential backoff (0.5, 1, 2, …) capped at 8s, with jitter."""
        import random
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except (TypeError, ValueError):
                pass
        return min(0.5 * (2 ** attempt), 8.0) + random.uniform(0, 0.25)
