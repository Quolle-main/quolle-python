# Quolle Python SDK

Official Python client for the [Quolle](https://quolle.com) email API.

## Install

```bash
pip install quolle
```

Requires Python 3.10+ (the oldest version still receiving security fixes). No third-party dependencies.

## Quick start

```python
from quolle import Quolle

quolle = Quolle(api_key="qle_...")  # or set QUOLLE_API_KEY

result = quolle.emails.send(
    from_="hello@mail.yourdomain.com",
    to="customer@example.com",
    subject="Welcome!",
    html="<h1>Thanks for signing up</h1>",
)
print("Queued:", result["id"])
```

> `from` is a reserved word in Python, so the SDK uses `from_`. Every other
> field matches the API.

## Sending

### Multiple recipients

```python
quolle.emails.send(
    from_="hello@mail.yourdomain.com",
    to=["a@example.com", "b@example.com"],
    subject="Announcement",
    html="<p>Hello everyone</p>",
)
```

### Templates

```python
quolle.emails.send(
    from_="hello@mail.yourdomain.com",
    to="customer@example.com",
    template="welcome-email",
    variables={"firstName": "Amaka", "planName": "Starter"},
)
```

### Scheduled send

```python
quolle.emails.send(
    from_="hello@mail.yourdomain.com",
    to="customer@example.com",
    subject="Your weekly digest",
    html="<p>Here's what happened this week.</p>",
    scheduled_at="2026-12-25T09:00:00.000Z",
)
```

### Idempotency

Pass an `idempotency_key` so retries never send twice:

```python
quolle.emails.send(
    from_="billing@mail.yourdomain.com",
    to="customer@example.com",
    subject="Invoice #1234",
    html="<p>Your invoice is attached.</p>",
    idempotency_key="order_invoice_12345",
)
```

### Batch

Up to 100 emails in one all-or-nothing request:

```python
result = quolle.emails.send_batch([
    {"from": "hello@mail.yourdomain.com", "to": "a@example.com",
     "subject": "Hi Alice", "html": "<p>Hi Alice</p>"},
    {"from": "hello@mail.yourdomain.com", "to": "b@example.com",
     "subject": "Hi Bob", "html": "<p>Hi Bob</p>"},
])
print(f"Queued {result['queued']}: {result['ids']}")
```

### Attachments

Attach files with `attachments` — a list of dicts (`filename`, base64 `content`,
optional `contentType`). Use `quolle.attachment()` to read and encode a file for you.
Up to 20 files, 10 MB total.

```python
from quolle import Quolle, attachment

quolle.emails.send(
    from_="billing@mail.yourdomain.com",
    to="customer@example.com",
    subject="Your invoice",
    html="<p>Invoice attached.</p>",
    attachments=[attachment("invoice.pdf")],
)
```

## Retrieve & cancel

```python
email = quolle.emails.get("a1b2c3d4-...")
print(email["status"])       # queued | sending | sent | delivered | bounced | failed
print(email["opensCount"])

quolle.emails.cancel("a1b2c3d4-...")  # only works while status == "scheduled"
```

## Error handling

```python
from quolle import Quolle, QuolleError

try:
    quolle.emails.send(from_="hello@mail.yourdomain.com",
                       to="customer@example.com",
                       subject="Welcome!", html="<h1>Welcome</h1>")
except QuolleError as err:
    print(err.status_code)  # e.g. 402
    print(err.code)         # e.g. "monthly_quota_exceeded" — branch on this
    print(err.message)      # e.g. "Monthly limit reached"
    print(err.data)         # extra fields, e.g. {"limit": 3000}
```

## Testing your integration

Send to a reserved test address to simulate any outcome without touching your
sending reputation:

- `delivered@test.quolle.com`
- `bounced@test.quolle.com`
- `complained@test.quolle.com`
- `suppressed@test.quolle.com`

## Verifying webhooks

Confirm an incoming webhook really came from Quolle. Pass the **raw** request body, the `Quolle-Signature` header, and your webhook signing secret (`whsec_…`, shown once when you created the webhook):

```python
from quolle import Quolle, QuolleError

quolle = Quolle(api_key="qle_...")

# In your webhook route (raw body — do not re-serialize):
try:
    event = quolle.webhooks.verify(
        raw_body,                          # bytes or str
        request.headers["Quolle-Signature"],
        "whsec_your_signing_secret",
    )
    print(event["event"])  # e.g. "email.delivered"
except QuolleError:
    ...  # reject the request (400)
```

Verification checks the HMAC-SHA256 signature and rejects timestamps outside a 5-minute window (replay protection).

## Domains, API keys and webhooks

These need a **full-access** API key. A sending-only key gets `403` with code `restricted_api_key`, so a key you ship in an app can't create keys or change your domains.

```python
# Domains
created = quolle.domains.create("mail.example.com")   # created["dnsRecords"] to publish
quolle.domains.verify(created["domain"]["id"])         # check DNS now
for d in quolle.domains.list():
    print(d["domain"], d["status"])

# API keys
new = quolle.api_keys.create("web app", scope="sending", domains=["mail.example.com"])
print(new["key"])                                      # shown once
quolle.api_keys.remove(new["id"])

# Webhook endpoints
hook = quolle.webhooks.create("https://example.com/hooks/quolle", ["email.delivered", "email.bounced"])
# hook["secret"] (whsec_…) is shown once; store it for quolle.webhooks.verify(...)
quolle.webhooks.test(hook["id"])
for d in quolle.webhooks.deliveries(hook["id"], status="failed"):
    quolle.webhooks.redeliver(hook["id"], d["id"])
new_secret = quolle.webhooks.rotate_secret(hook["id"])["secret"]
```

## Automatic retries

Transient failures — HTTP 429 (rate limit) and 5xx, plus network errors — are retried automatically with exponential backoff, honoring the `Retry-After` header. To avoid double-sending, a POST is only retried on a 5xx/network error when you pass an idempotency key; a 429 is always safe to retry (the request was never processed). Quota limits are the exception: `daily_quota_exceeded` and `warmup_limit_exceeded` (and any `Retry-After` over 60 seconds) are raised immediately, because they reset at a fixed time, not in seconds; catch them and queue the send for later. Tune with `max_retries` (default 3) on the constructor.

## License

MIT
# quolle-python
