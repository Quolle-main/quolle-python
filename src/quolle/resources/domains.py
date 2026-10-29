"""Sending domains. Needs a full-access API key."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List
from urllib.parse import quote as _urlquote

if TYPE_CHECKING:  # pragma: no cover
    from ..client import Quolle


def _q(value: str) -> str:
    return _urlquote(str(value), safe="")


class Domains:
    """Add, inspect, verify and remove sending domains (``client.domains``)."""

    def __init__(self, client: "Quolle") -> None:
        self._client = client

    def list(self) -> List[Dict[str, Any]]:
        """Every sending domain, with its verification and warm-up state."""
        return self._client.request("GET", "/v1/domains").get("domains", [])

    def create(self, domain: str) -> Dict[str, Any]:
        """Add a domain (e.g. ``mail.example.com``). Returns ``domain`` and the ``dnsRecords`` to publish."""
        return self._client.request("POST", "/v1/domains", {"domain": domain})

    def get(self, domain_id: str) -> Dict[str, Any]:
        """One domain by id."""
        return self._client.request("GET", f"/v1/domains/{_q(domain_id)}").get("domain", {})

    def records(self, domain_id: str) -> Dict[str, Any]:
        """The DNS records to publish, and which of them are found."""
        return self._client.request("GET", f"/v1/domains/{_q(domain_id)}/records")

    def verify(self, domain_id: str) -> Dict[str, Any]:
        """Check DNS again now instead of waiting for the next automatic check."""
        return self._client.request("POST", f"/v1/domains/{_q(domain_id)}/recheck")

    def remove(self, domain_id: str) -> Dict[str, Any]:
        """Remove a domain. Mail can no longer be sent from it."""
        return self._client.request("DELETE", f"/v1/domains/{_q(domain_id)}")
