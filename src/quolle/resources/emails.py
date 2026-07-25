"""Email operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

if TYPE_CHECKING:  # pragma: no cover
    from ..client import Quolle

Recipient = Union[str, Sequence[str]]


def attachment(
    path: str,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    content_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build an attachment dict from a file on disk.

    Reads the file, base64-encodes it, and guesses the content type from the
    filename. Pass the result(s) to ``emails.send(attachments=[...])``.

    Set ``content_id`` to embed the file inline — reference it in your HTML with
    ``<img src="cid:the-id">``.

    To attach a remote file instead, skip this helper and pass a dict with a
    ``path`` (URL) and ``filename`` — Quolle fetches it at send time.
    """
    import base64
    import mimetypes
    import os

    with open(path, "rb") as f:
        data = f.read()
    name = filename or os.path.basename(path)
    ctype = content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    att: Dict[str, Any] = {
        "filename": name,
        "content": base64.b64encode(data).decode("ascii"),
        "contentType": ctype,
    }
    if content_id is not None:
        att["contentId"] = content_id
    return att


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
    attachments: Optional[List[Dict[str, Any]]] = None,
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
    if attachments is not None:
        payload["attachments"] = attachments
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
        attachments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Queue an email for immediate or scheduled delivery.

        Provide either ``html`` (with ``subject``) or a ``template`` slug (with
        optional ``variables``). Returns a dict with at least ``id`` and
        ``message``; scheduled sends also return ``scheduledAt`` and ``status``.

        ``attachments`` is a list of dicts, each with ``filename``, ``content``
        (the file bytes base64-encoded as a string), and an optional
        ``contentType``. Use :func:`quolle.attachment` to build one from a file.
        Up to 20 attachments, 10 MB total.

        Pass ``idempotency_key`` to make retries safe — the same key returns the
        original result instead of sending twice.
        """
        payload = _build_payload(
            from_, to, subject, html, text, template, variables,
            reply_to, scheduled_at, attachments, metadata,
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
