# vendored/email_send.py

**Source**: `openclaw/openclaw` — commit `b2e8b7d4bb2f22eaa16f5c4b07547774e90b65a5`  
**Type**: Functional reproduction — NOT a literal port  
**Upstream**: <https://github.com/openclaw/openclaw>

## Why is this here?

OpenClaw is a TypeScript framework. There is no official Python SDK and no
email-send primitive in the upstream repository at the pinned commit.

Rather than pretending to import something that does not exist, this file
provides a **functionally equivalent** Python reproduction of the email-send
flow so that the `demos/openclaw/run.py` scenario works end-to-end without
any network call or mock patching.

The reproduction preserves the observable contract that matters for the demo:

| Behaviour | upstream (TS) | this file (Python) |
|---|---|---|
| `agent_send_email(client, to, subject, body, acting_on_behalf_of=...)` call signature | ✓ | ✓ |
| Appends the message to an in-memory list on success | ✓ (HTTP call) | ✓ (in-memory list) |
| Returns a dict with at least `{"status": "sent", "message_id": ...}` | ✓ | ✓ |
| Does NOT interact with an SMTP server | N/A | ✓ |

If openclaw/openclaw ever publishes an official Python SDK with an email
extension, replace this file with a real import and delete this README.
