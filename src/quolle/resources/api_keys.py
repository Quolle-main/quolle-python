"""API keys. Needs a full-access key; a sending-only key gets 403 restricted_api_key."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional
from urllib.parse import quote as _urlquote

if TYPE_CHECKING:  # pragma: no cover
    from ..client import Quolle


class ApiKeys:
    """List, create and revoke API keys (``client.api_keys``)."""

    def __init__(self, client: "Quolle") -> None:
        self._client = client

    def list(self) -> List[Dict[str, Any]]:
        """Active keys. The keys themselves are never returned, only a ``preview``."""
        return self._client.request("GET", "/v1/keys").get("keys", [])

    def create(
        self,
        name: str,
        *,
        scope: Optional[Literal["full", "sending"]] = None,
        domains: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a key. The returned ``key`` (``qle_…``) is shown once; store it now.

        ``scope="sending"`` makes a key that can only send email and read its
        status; ``domains`` limits it to those sending domains.
        """
        body: Dict[str, Any] = {"name": name}
        if scope is not None:
            body["scope"] = scope
        if domains is not None:
            body["domains"] = list(domains)
        if expires_in_days is not None:
            body["expiresInDays"] = expires_in_days
        return self._client.request("POST", "/v1/keys", body)

    def remove(self, key_id: str) -> Dict[str, Any]:
        """Revoke a key. Requests made with it fail from now on."""
        return self._client.request("DELETE", f"/v1/keys/{_urlquote(str(key_id), safe='')}")
