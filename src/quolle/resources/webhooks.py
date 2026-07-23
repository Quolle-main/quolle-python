"""Webhook signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Union

from ..errors import QuolleError

DEFAULT_TOLERANCE = 300  # seconds


def _parse_header(header: str) -> tuple[str, str]:
    """Parse a `Quolle-Signature` header of the form 't=<ts>,v1=<hex>'."""
    parts = dict(
        p.split("=", 1) for p in header.split(",") if "=" in p
    )
    t = parts.get("t", "")
    v1 = parts.get("v1", "")
    if not t or not v1:
        raise QuolleError("Invalid Quolle-Signature header")
    return t, v1


class Webhooks:
    """Verify that an incoming webhook really came from Quolle."""

    def verify(
        self,
        payload: Union[str, bytes],
        signature_header: str,
        secret: str,
        tolerance: int = DEFAULT_TOLERANCE,
    ) -> Dict[str, Any]:
        """Verify a webhook's signature and return the parsed event.

        Pass the RAW request body (bytes or str), the value of the
        ``Quolle-Signature`` request header, and your webhook signing secret
        (``whsec_…``, shown once when you created the webhook).

        Raises:
            QuolleError: if the header is malformed, the timestamp is outside the
                tolerance window (replay protection), or the signature doesn't match.
        """
        body = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        t, v1 = _parse_header(signature_header)

        try:
            ts = int(t)
        except ValueError:
            raise QuolleError("Invalid timestamp in Quolle-Signature header") from None
        if abs(time.time() - ts) > tolerance:
            raise QuolleError("Webhook timestamp outside the tolerance window (possible replay)")

        expected = hmac.new(
            secret.encode("utf-8"), f"{ts}.{body}".encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, v1):
            raise QuolleError("Webhook signature verification failed")

        return json.loads(body)
