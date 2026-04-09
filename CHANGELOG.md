# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2024-04-09

### Added
- Initial release
- Payment policies: `payment.amount_limit`, `payment.velocity`, `payment.daily_limit`, `payment.duplicate_detection`, `payment.recipient_blocklist`
- Email policies: `email.domain_blocklist`, `email.rate_limit`, `email.business_hours`, `email.content_scan`
- YAML policy loader
- SQLite audit trail
- `@gate()` decorator
- Three-verdict system: CONTINUE / REVIEW / STOP
