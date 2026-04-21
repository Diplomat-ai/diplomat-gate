# Security Policy

## Reporting a vulnerability

Do not open a public GitHub issue for security vulnerabilities.

**Email**: josselin@diplomat.run
**Response time**: 48 hours

## Scope

diplomat-gate runs entirely locally. It makes no network calls and collects no telemetry. It evaluates policy rules against plain Python dicts — it does not execute agent code.

Vulnerabilities in scope:
- Policy bypass: crafted input that circumvents a policy check (e.g. amount limit not enforced)
- Audit integrity: tampering with or corrupting the SQLite audit trail
- Glob/pattern escape: recipient or domain patterns that can be evaded

## Out of scope

- Vulnerabilities in the agent code being protected (diplomat-gate evaluates, it doesn't patch)
- Feature requests (use GitHub issues)
