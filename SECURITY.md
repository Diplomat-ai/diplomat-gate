# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.3.x | yes |
| < 0.3 | no |

## Reporting a vulnerability

**Do not open a public GitHub issue.**

Email the maintainer at **josselin@diplomat.run** with:

- A description of the vulnerability
- Steps to reproduce
- The version(s) affected
- Your disclosure timeline expectations

You should receive an acknowledgment within 72 hours. A mitigation or
clarification within 7 days for critical issues, 30 days otherwise.

## Scope

diplomat-gate is an enforcement layer that evaluates policies against tool
calls. Security issues in scope include:

- Policy bypass (a policy marked STOP allows the action through)
- Audit log tampering (modifying the SQLite database without detection)
- Incorrect verdict (a valid STOP wrongly returned as CONTINUE)
- Information disclosure in audit or review storage beyond documented
  redaction

**Out of scope** -- known and documented limits (see README.md Limitations):

- Semantic attacks (an agent sends to a domain that doesn't match any
  blocklist pattern -- design your allowlists properly)
- Local attacker with write access to the audit DB (rebuild-chain is
  intentional; ship records to a write-once store if you need strong
  tamper-evidence)
- Concurrent rate-limit accuracy in multi-process setups (wrap with an
  external lock or store)

## Responsible disclosure

I commit to:

- Acknowledging your report within 72 hours
- Providing a timeline for the fix
- Crediting you in the release notes unless you prefer anonymity
- Publishing a GitHub Security Advisory once a patch is available

I ask you to:

- Not exploit the issue beyond confirming it exists
- Not disclose publicly until a fix is released (or 90 days, whichever is
  shorter)
- Test only on your own systems
