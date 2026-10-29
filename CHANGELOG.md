# Changelog

All notable changes to this package. Versions follow [Semantic Versioning](https://semver.org).

## 1.2.0 — 2026-10-29

### Added
- `QuolleError.code`: the API's machine-readable error code.
- `emails.send(message_type="marketing")`, validated.

### Changed
- Quota limits are no longer retried. `daily_quota_exceeded` and `warmup_limit_exceeded` (and any 429 whose `Retry-After` is over 60 seconds) are raised at once with their code, instead of the client waiting, possibly for hours, before failing. Ordinary rate limits are still retried.
- **Requires Python 3.10+** (was 3.8). 3.8 and 3.9 are past end of life; pip keeps older interpreters on 1.1.0.
- A 2xx response that isn't JSON now raises instead of crashing.

### Fixed
- Email ids are URL-encoded in request paths.
- A read timeout is reported as a `QuolleError`.
- PyPI project links point at `github.com/Quolle-main/quolle-python` and quolle.com/docs.

## 1.1.0

Attachments: `attachment()` helper and `attachments` parameter.
