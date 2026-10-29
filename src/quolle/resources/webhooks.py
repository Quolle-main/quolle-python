"""Webhook endpoints and signature verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import quote as _urlquote

from ..errors import QuolleError

if TYPE_CHECKING:  # pragma: no cover
    from ..client import Quolle

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


def _q(value: str) -> str:
    return _urlquote(str(value), safe="")


class Webhooks:
    """Verify incoming webhooks, and manage webhook endpoints (``client.webhooks``).

    ``verify`` needs no API call. The management methods need a full-access key.
    """

    def __init__(self, client: Optional["Quolle"] = None) -> None:
        self._client = client

    def _req(self, method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._client is None:
            raise QuolleError("Webhooks() was created without a client; use Quolle(...).webhooks")
        return self._client.request(method, path, body)

    def events(self) -> List[Dict[str, Any]]:
        """The event names a webhook can subscribe to."""
        return self._req("GET", "/v1/webhooks/events").get("events", [])

    def list(self) -> List[Dict[str, Any]]:
        return self._req("GET", "/v1/webhooks").get("webhooks", [])

    def create(self, url: str, events: List[str]) -> Dict[str, Any]:
        """Add an endpoint. The returned ``secret`` (``whsec_…``) is shown once; store it."""
        return self._req("POST", "/v1/webhooks", {"url": url, "events": list(events)})

    def get(self, webhook_id: str) -> Dict[str, Any]:
        return self._req("GET", f"/v1/webhooks/{_q(webhook_id)}")

    def update(self, webhook_id: str, *, url: Optional[str] = None, events: Optional[List[str]] = None) -> Dict[str, Any]:
        """Change the URL or events. The signing secret stays the same."""
        body: Dict[str, Any] = {}
        if url is not None:
            body["url"] = url
        if events is not None:
            body["events"] = list(events)
        return self._req("PATCH", f"/v1/webhooks/{_q(webhook_id)}", body)

    def remove(self, webhook_id: str) -> Dict[str, Any]:
        return self._req("DELETE", f"/v1/webhooks/{_q(webhook_id)}")

    def test(self, webhook_id: str) -> Dict[str, Any]:
        """Send a signed ``webhook.test`` event now and report how the endpoint answered."""
        return self._req("POST", f"/v1/webhooks/{_q(webhook_id)}/test")

    def deliveries(self, webhook_id: str, *, status: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Deliveries from the last 30 days, newest first. ``status``: succeeded, pending or failed."""
        from urllib.parse import urlencode

        params = {k: v for k, v in (("status", status), ("limit", limit)) if v is not None}
        qs = f"?{urlencode(params)}" if params else ""
        return self._req("GET", f"/v1/webhooks/{_q(webhook_id)}/deliveries{qs}").get("deliveries", [])

    def redeliver(self, webhook_id: str, delivery_id: str) -> Dict[str, Any]:
        """Send a delivery again, with the same body and ``eventId``."""
        return self._req("POST", f"/v1/webhooks/{_q(webhook_id)}/deliveries/{_q(delivery_id)}/redeliver")

    def rotate_secret(self, webhook_id: str) -> Dict[str, Any]:
        """Replace the signing secret. Takes effect immediately; the new ``secret`` is returned once."""
        return self._req("POST", f"/v1/webhooks/{_q(webhook_id)}/rotate-secret")

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
