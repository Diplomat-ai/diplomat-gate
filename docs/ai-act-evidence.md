# EU AI Act — which evidence diplomat-gate can produce

**status: draft — pending legal review**

> **Read this first.** This page describes *technical evidence artifacts*
> that diplomat-gate produces. It is **not legal advice**. diplomat-gate is
> a component, not an AI system whose risk category we assess here: whether
> your system falls under the high-risk rules, and how obligations are split
> between provider and deployer, must be determined for your own case by a
> lawyer or your data protection officer. Article numbers refer to
> Regulation (EU) 2024/1689 (AI Act) and Regulation (EU) 2016/679 (GDPR) as
> we understand them today, and are themselves subject to that review.

## How to read the table

Each row starts from a requirement a provider or deployer may have to
document, names the diplomat-gate artifact that can feed that
documentation, says where to find it in this repository, and — in the
last column, which is never empty — says what the artifact does **not**
cover. An artifact is evidence you can attach to your own file; it does
not by itself discharge an obligation.

| Requirement (as we read it) | diplomat-gate artifact | Where to find it | What it does not cover |
| --- | --- | --- | --- |
| Automatic recording of events over the lifetime of the system (AI Act Art. 12, record-keeping) | `AuditLog`: every verdict is stored in an append-only SQLite table, each row sealed by a SHA-256 hash chained on the previous row. The format is published as a versioned specification and can be verified by a third party with a single-file, standard-library-only script. | `src/diplomat_gate/audit.py`, `docs/receipt-format.md`, `tools/verify_receipts.py`, `docs/audit-trail.md` | Records only tool-call verdicts, not model inputs or outputs or the rest of your system. Does not decide which events your risk assessment requires. Does not manage retention periods (see AI Act Art. 19 and Art. 26). An attacker with write access who rewrites the whole chain, or deletes the last records, is not detected without an externally archived copy of a recent hash. No signature and no trusted timestamp. |
| Human oversight, including the ability to intervene or stop (AI Act Art. 14) | A `REVIEW` verdict raises `NeedsReview` and holds the call. When a review queue is configured, the call is queued in a `ReviewQueue` with the lifecycle pending → approved / rejected / expired. The reviewer name, timestamp and note are recorded. | `src/diplomat_gate/review.py`, `src/diplomat_gate/decorator.py`, `docs/review-queue.md`, `src/diplomat_gate/cli.py` | Art. 14 is about how the system is designed so that competent people can oversee it effectively; competence, training and awareness of automation bias are outside this library. The queue is a separate, mutable SQLite file, not covered by the audit hash chain. The reviewer name is free text and is not authenticated. There are no notifications. Approving an item does not re-run the action. |
| Minimising personal data kept in logs (GDPR Art. 5(1)(c); interacts with the logging obligation above) | Default redaction: values of the sensitive keys listed in `SENSITIVE_FIELDS` are replaced by a truncated SHA-256 marker before they are persisted in violation contexts (audit log) and, for the review queue, in the parameters as well. | `src/diplomat_gate/models.py`, `src/diplomat_gate/audit.py`, `src/diplomat_gate/review.py` | The list covers only seven keys unless you extend it; other personal data in your parameters is not redacted. The marker is a pseudonym, not anonymisation: values with a small domain (an amount, a phone number, the last four digits of a card) can be recovered by brute force. `agent_id`, `action` and `params_hash` are stored in clear. Redaction can be switched off by the integrator. |

## What is not in this table

- **Risk classification.** Nothing here tells you whether your system is
  high-risk.
- **Conformity assessment, technical documentation, quality management,
  post-market monitoring.** diplomat-gate produces raw evidence for some
  of these files; it does not write or replace them.
- **Centralised, externally anchored storage and long-term retention.**
  The local audit log is a single SQLite file on your infrastructure.
  Anything beyond that — for example archiving hashes to an append-only
  store you control — is your responsibility or that of a separate
  service.

## Status of this page

This is a working draft. Do not rely on the mapping above, and do not
quote it externally, until it has been reviewed by qualified counsel.
