"""Domains, API keys and webhook endpoint management (K8): each method hits the right route."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quolle import Quolle, QuolleError  # noqa: E402


class _Resp:
    def __init__(self, payload, status=200):
        self.status = status
        self._raw = json.dumps(payload).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def calls(monkeypatch):
    import urllib.request

    seen = []

    def fake_urlopen(req, timeout=None):
        from urllib.parse import urlsplit

        u = urlsplit(req.full_url)
        seen.append((req.get_method(), u.path + (f"?{u.query}" if u.query else ""),
                     json.loads(req.data.decode()) if req.data else None))
        return _Resp({"domains": [{"id": "d1"}], "domain": {"id": "d1"}, "keys": [{"id": "k1"}],
                      "webhooks": [], "deliveries": [], "events": []})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return seen


def test_domains(calls):
    q = Quolle(api_key="qle_test")
    assert q.domains.list()[0]["id"] == "d1"
    q.domains.create("mail.acme.com")
    assert q.domains.get("d1")["id"] == "d1"
    q.domains.records("d1")
    q.domains.verify("d1")
    q.domains.remove("d1")
    assert [(m, p) for m, p, _ in calls] == [
        ("GET", "/v1/domains"), ("POST", "/v1/domains"), ("GET", "/v1/domains/d1"),
        ("GET", "/v1/domains/d1/records"), ("POST", "/v1/domains/d1/recheck"), ("DELETE", "/v1/domains/d1"),
    ]
    assert calls[1][2] == {"domain": "mail.acme.com"}


def test_api_keys(calls):
    q = Quolle(api_key="qle_test")
    assert q.api_keys.list()[0]["id"] == "k1"
    q.api_keys.create("ci", scope="sending", domains=["mail.acme.com"], expires_in_days=30)
    q.api_keys.remove("k1")
    assert [(m, p) for m, p, _ in calls] == [("GET", "/v1/keys"), ("POST", "/v1/keys"), ("DELETE", "/v1/keys/k1")]
    assert calls[1][2] == {"name": "ci", "scope": "sending", "domains": ["mail.acme.com"], "expiresInDays": 30}


def test_webhook_endpoints(calls):
    q = Quolle(api_key="qle_test")
    q.webhooks.events()
    q.webhooks.list()
    q.webhooks.create("https://x.io/h", ["email.delivered"])
    q.webhooks.get("w1")
    q.webhooks.update("w1", events=["email.bounced"])
    q.webhooks.test("w1")
    q.webhooks.deliveries("w1", status="failed", limit=10)
    q.webhooks.redeliver("w1", "dl1")
    q.webhooks.rotate_secret("w1")
    q.webhooks.remove("w1")
    assert [(m, p) for m, p, _ in calls] == [
        ("GET", "/v1/webhooks/events"), ("GET", "/v1/webhooks"), ("POST", "/v1/webhooks"),
        ("GET", "/v1/webhooks/w1"), ("PATCH", "/v1/webhooks/w1"), ("POST", "/v1/webhooks/w1/test"),
        ("GET", "/v1/webhooks/w1/deliveries?status=failed&limit=10"),
        ("POST", "/v1/webhooks/w1/deliveries/dl1/redeliver"), ("POST", "/v1/webhooks/w1/rotate-secret"),
        ("DELETE", "/v1/webhooks/w1"),
    ]
    assert calls[4][2] == {"events": ["email.bounced"]}


def test_restricted_key_error_code(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    def fake_urlopen(req, timeout=None):
        body = json.dumps({"code": "restricted_api_key", "error": "This API key can only send email."}).encode()
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(QuolleError) as exc:
        Quolle(api_key="qle_test").api_keys.list()
    assert exc.value.code == "restricted_api_key"
    assert exc.value.status_code == 403


def test_verify_still_works_without_a_client():
    from quolle.resources.webhooks import Webhooks

    with pytest.raises(QuolleError):
        Webhooks().list()
