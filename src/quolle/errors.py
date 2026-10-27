"""Error types raised by the Quolle SDK."""

from __future__ import annotations

from typing import Any, Dict, Optional


class QuolleError(Exception):
    """Raised when the Quolle API returns a non-2xx response, or the request
    could not be completed (network/timeout).

    Attributes:
        message: Human-readable error message (from the API's ``error`` field).
        status_code: HTTP status code, or ``None`` for transport-level failures.
        code: The API's stable, machine-readable error code (e.g.
            ``"validation_error"``, ``"rate_limit_exceeded"``). Branch on this,
            not on the message. ``None`` for transport-level failures.
        data: Any extra fields the API returned alongside ``error`` (e.g. limit
            details on a 402, validation ``errors`` on a 422).
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.data: Dict[str, Any] = data or {}

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.status_code is not None and self.code:
            return f"[{self.status_code} {self.code}] {self.message}"
        if self.status_code is not None:
            return f"[{self.status_code}] {self.message}"
        return self.message
