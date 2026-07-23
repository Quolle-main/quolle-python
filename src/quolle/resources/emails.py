"""Email operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

if TYPE_CHECKING:  # pragma: no cover
    from ..client import Quolle

Recipient = Union[str, Sequence[str]]


def _build_payload(
    from_: str,
    to: Recipient,
    subject: Optional[str] = None,
    html: Optional[str] = None,
    text: Optional[str] = None,
    template: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    reply_to: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    # ``from`` is a Python keyword, so the SDK accepts ``from_`` and maps it.
    payload: Dict[str, Any] = {"from": from_, "to": list(to) if not isinstance(to, str) else to}
    if subject is not None:
        payload["subject"] = subject
    if html is not None:
        payload["html"] = html
    if text is not None:
        payload["text"] = text
    if template is not None:
        payload["template"] = template
    if variables is not None:
        payload["variables"] = variables
    if reply_to is not None:
        payload["replyTo"] = reply_to
    if scheduled_at is not None:
        payload["scheduledAt"] = scheduled_at
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


class Emails:
    """Send and manage emails."""

    def __init__(self, client: "Quolle") -> None:
        self._client = client

    def send(
        self,
        from_: str,
        to: Recipient,
        subject: Optional[str] = None,
        html: Optional[str] = None,
        text: Optional[str] = None,
        template: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        reply_to: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Queue an email for immediate or scheduled delivery.

        Provide either ``html`` (with ``subject``) or a ``template`` slug (with
        optional ``variables``). Returns a dict with at least ``id`` and
        ``message``; scheduled sends also return ``scheduledAt`` and ``status``.

        Pass ``idempotency_key`` to make retries safe — the same key returns the
        original result instead of sending twice.
        """
        payload = _build_payload(
            from_, to, subject, html, text, template, variables,
            reply_to, scheduled_at, metadata,
        )
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.request("POST", "/v1/emails/send", payload, headers)

    def send_batch(
        self,
        emails: List[Dict[str, Any]],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send up to 100 emails in one all-or-nothing request.

        Each item is a dict of the same fields ``send`` accepts, but using the
        raw API names (``from``, ``replyTo``, ``scheduledAt``). Returns
        ``{"queued": <count>, "ids": [...]}``.
        """
        body = {"emails": emails}
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return self._client.request("POST", "/v1/emails/batch", body, headers)

    def get(self, email_id: str) -> Dict[str, Any]:
        """Retrieve a single email by ID (status, timestamps, open/click counts)."""
        resp = self._client.request("GET", f"/v1/emails/{email_id}")
        return resp.get("email", resp)

    def cancel(self, email_id: str) -> Dict[str, Any]:
        """Cancel a scheduled email that has not yet been sent."""
        return self._client.request("DELETE", f"/v1/emails/{email_id}/cancel")
