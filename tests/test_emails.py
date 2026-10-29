"""Unit tests for the Quolle Python SDK — no network calls; the transport
layer is stubbed so we assert exactly what the SDK sends and how it parses."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quolle import Quolle, QuolleError  # noqa: E402


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def patch_transport(monkeypatch, capture, *, status=200, payload=None):
    """Replace urlopen so tests run fully offline."""
    import urllib.request

    def fake_urlopen(req, timeout=None):
        capture["method"] = req.get_method()
        capture["url"] = req.full_url
        capture["headers"] = {k.lower(): v for k, v in req.headers.items()}
        capture["body"] = json.loads(req.data.decode()) if req.data else None
        return FakeResponse(status, payload or {})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("QUOLLE_API_KEY", raising=False)
    with pytest.raises(ValueError):
        Quolle()


def test_send_maps_fields_and_auth(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"id": "em_1", "message": "Email queued successfully"})
    q = Quolle(api_key="qle_test")

    result = q.emails.send(
        from_="hello@mail.acme.com",
        to="user@example.com",
        subject="Hi",
        html="<p>Hi</p>",
        reply_to="support@acme.com",
    )

    assert result["id"] == "em_1"
    assert cap["method"] == "POST"
    assert cap["url"].endswith("/v1/emails/send")
    assert cap["headers"]["authorization"] == "Bearer qle_test"
    # from_ -> from, reply_to -> replyTo
    assert cap["body"]["from"] == "hello@mail.acme.com"
    assert cap["body"]["replyTo"] == "support@acme.com"
    assert "text" not in cap["body"]  # omitted optionals are not sent


def test_idempotency_header(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"id": "em_2"})
    q = Quolle(api_key="qle_test")
    q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>",
                  idempotency_key="order_123")
    assert cap["headers"]["idempotency-key"] == "order_123"


def test_send_batch(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"queued": 2, "ids": ["a", "b"]})
    q = Quolle(api_key="qle_test")
    out = q.emails.send_batch([
        {"from": "a@b.com", "to": "x@y.com", "subject": "1", "html": "<p>1</p>"},
        {"from": "a@b.com", "to": "z@y.com", "subject": "2", "html": "<p>2</p>"},
    ])
    assert out["queued"] == 2
    assert cap["url"].endswith("/v1/emails/batch")
    assert len(cap["body"]["emails"]) == 2


def test_get_unwraps_email(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"email": {"id": "em_1", "status": "delivered"}})
    q = Quolle(api_key="qle_test")
    email = q.emails.get("em_1")
    assert email["status"] == "delivered"  # unwrapped from {"email": ...}
    assert cap["method"] == "GET"


def test_cancel(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"message": "Scheduled email cancelled"})
    q = Quolle(api_key="qle_test")
    out = q.emails.cancel("em_1")
    assert out["message"] == "Scheduled email cancelled"
    assert cap["method"] == "DELETE"


def test_error_raises_quolle_error(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 402, "Payment Required", {},
            io_bytes(json.dumps({"error": "Monthly limit reached", "limit": 3000})),
        )

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    q = Quolle(api_key="qle_test")
    with pytest.raises(QuolleError) as exc:
        q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>")
    assert exc.value.status_code == 402
    assert "Monthly limit" in exc.value.message
    assert exc.value.data["limit"] == 3000


def io_bytes(s):
    import io
    return io.BytesIO(s.encode("utf-8"))


def _http_error(status, reason, body=""):
    import urllib.error
    return urllib.error.HTTPError("http://x", status, reason, {}, io_bytes(body))


def test_retries_on_429_then_succeeds(monkeypatch):
    import urllib.request
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(429, "Too Many Requests", json.dumps({"error": "rate limited"}))
        return FakeResponse(200, {"id": "em_ok"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: None)  # no real waiting

    q = Quolle(api_key="qle_test")
    out = q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>")
    assert out["id"] == "em_ok"
    assert calls["n"] == 3  # two 429s + one success


def test_does_not_retry_5xx_on_post_without_idempotency(monkeypatch):
    import urllib.request
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise _http_error(500, "Server Error", json.dumps({"error": "boom"}))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    q = Quolle(api_key="qle_test")
    with pytest.raises(QuolleError):
        q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>")
    assert calls["n"] == 1  # POST 5xx without idempotency key must NOT retry (no double-send)


def test_retries_5xx_on_post_when_idempotent(monkeypatch):
    import urllib.request
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 2:
            raise _http_error(503, "Unavailable", json.dumps({"error": "try later"}))
        return FakeResponse(200, {"id": "em_ok"})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    q = Quolle(api_key="qle_test")
    out = q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>",
                        idempotency_key="order_1")
    assert out["id"] == "em_ok"
    assert calls["n"] == 2  # 5xx retried because an idempotency key is present


# ── Webhook signature verification ────────────────────────────────────────────

import hmac as _hmac, hashlib as _hashlib, time as _time


def _sign(secret, ts, body):
    return _hmac.new(secret.encode(), f"{ts}.{body}".encode(), _hashlib.sha256).hexdigest()


def test_webhook_verify_valid():
    q = Quolle(api_key="qle_test")
    secret, body = "whsec_x", json.dumps({"event": "email.delivered"})
    ts = int(_time.time())
    evt = q.webhooks.verify(body, f"t={ts},v1={_sign(secret, ts, body)}", secret)
    assert evt["event"] == "email.delivered"


def test_webhook_verify_rejects_tamper():
    q = Quolle(api_key="qle_test")
    secret, body = "whsec_x", json.dumps({"event": "email.delivered"})
    ts = int(_time.time())
    header = f"t={ts},v1={_sign(secret, ts, body)}"
    with pytest.raises(QuolleError):
        q.webhooks.verify(body + "tampered", header, secret)


def test_webhook_verify_rejects_stale_timestamp():
    q = Quolle(api_key="qle_test")
    secret, body = "whsec_x", json.dumps({"event": "email.delivered"})
    old = int(_time.time()) - 10_000
    with pytest.raises(QuolleError):
        q.webhooks.verify(body, f"t={old},v1={_sign(secret, old, body)}", secret)


def test_webhook_verify_rejects_wrong_secret():
    q = Quolle(api_key="qle_test")
    body = json.dumps({"event": "email.delivered"})
    ts = int(_time.time())
    header = f"t={ts},v1={_sign('whsec_right', ts, body)}"
    with pytest.raises(QuolleError):
        q.webhooks.verify(body, header, "whsec_wrong")


# ── Alignment with the API (error code, message type, ids, bad responses) ─────

def test_error_exposes_the_api_code(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    def fake_urlopen(req, timeout=None):
        body = json.dumps({"code": "warmup_limit_exceeded", "error": "Warm-up cap reached"}).encode()
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    q = Quolle(api_key="qle_test", max_retries=0)
    with pytest.raises(QuolleError) as exc:
        q.emails.send(from_="a@b.co", to="c@d.co", subject="s", html="<p>x</p>")
    assert exc.value.code == "warmup_limit_exceeded"
    assert exc.value.status_code == 429
    assert "code" not in exc.value.data


def test_marketing_type_is_sent_and_validated(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"id": "em_2"})
    q = Quolle(api_key="qle_test")
    q.emails.send(from_="a@b.co", to="c@d.co", subject="s", html="<p>x</p>", message_type="marketing")
    assert cap["body"]["type"] == "marketing"
    with pytest.raises(ValueError):
        q.emails.send(from_="a@b.co", to="c@d.co", subject="s", html="<p>x</p>", message_type="promo")


def test_transactional_by_default_omits_type(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"id": "em_3"})
    Quolle(api_key="qle_test").emails.send(from_="a@b.co", to="c@d.co", subject="s", html="<p>x</p>")
    assert "type" not in cap["body"]


def test_email_ids_are_url_encoded(monkeypatch):
    cap = {}
    patch_transport(monkeypatch, cap, payload={"email": {"id": "x"}})
    Quolle(api_key="qle_test").emails.get("../keys?x=1")
    assert cap["url"].endswith("/v1/emails/..%2Fkeys%3Fx%3D1")


def test_non_json_success_raises(monkeypatch):
    import urllib.request

    class Html(FakeResponse):
        def __init__(self):
            self.status = 200
            self._raw = b"<html>proxy error</html>"

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Html())
    with pytest.raises(QuolleError):
        Quolle(api_key="qle_test").emails.get("em_1")


def test_socket_timeout_becomes_a_quolle_error(monkeypatch):
    import socket
    import urllib.request

    def boom(req, timeout=None):
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(QuolleError):
        Quolle(api_key="qle_test", max_retries=0).emails.get("em_1")


# ── Quota 429s are not retried (they reset at a fixed time, not in seconds) ───

@pytest.mark.parametrize("code", ["daily_quota_exceeded", "warmup_limit_exceeded"])
def test_quota_429_is_raised_at_once_not_retried(monkeypatch, code):
    import urllib.request
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise _http_error(429, "Too Many Requests", json.dumps({"code": code, "error": "cap reached"}))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: pytest.fail("must not sleep"))
    q = Quolle(api_key="qle_test")
    with pytest.raises(QuolleError) as exc:
        q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>")
    assert exc.value.code == code
    assert calls["n"] == 1


def test_429_with_a_long_retry_after_is_raised_not_slept_through(monkeypatch):
    import io
    import urllib.error
    import urllib.request
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        body = json.dumps({"code": "rate_limit_exceeded", "error": "slow down"}).encode()
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {"Retry-After": "3600"}, io.BytesIO(body))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: pytest.fail("must not sleep an hour"))
    q = Quolle(api_key="qle_test")
    with pytest.raises(QuolleError):
        q.emails.send(from_="a@b.com", to="c@d.com", subject="s", html="<p>x</p>")
    assert calls["n"] == 1
