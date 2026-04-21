# Writing Policies

This guide explains how to create custom policies for diplomat-gate.

## Policy anatomy

Every policy extends `Policy` from `diplomat_gate.policies.base`:

```python
from dataclasses import dataclass
from diplomat_gate.models import PolicyResult, ToolCall
from diplomat_gate.state import StateStore
from diplomat_gate.policies.base import Policy


@dataclass
class MyPolicy(Policy):
    threshold: float = 100.0

    def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
        value = tool_call.params.get("some_param", 0)
        return PolicyResult.FAIL if float(value) > self.threshold else PolicyResult.PASS

    def violation_message(self, tool_call: ToolCall) -> str:
        return f"Value exceeds threshold of {self.threshold}"
```

## Required fields (inherited from Policy)

| Field | Type | Description |
|-------|------|-------------|
| `policy_id` | `str` | Unique dot-namespaced ID, e.g. `"myorg.my_policy"` |
| `name` | `str` | Human-readable name |
| `domain` | `str` | `"payment"`, `"email"`, or `"any"` |
| `severity` | `str` | `"critical"`, `"high"`, `"medium"`, `"low"` |
| `on_fail` | `str` | `"STOP"` or `"REVIEW"` |
| `enabled` | `bool` | Toggle the policy on/off |

## The three results

- `PolicyResult.PASS` — policy is satisfied, no action
- `PolicyResult.FAIL` — policy failed; triggers `on_fail` action
- `PolicyResult.WARN` — soft failure; also triggers `on_fail` action

## Using the state store

Stateful policies (rate limits, dedup) use the shared `StateStore`:

```python
def evaluate(self, tool_call: ToolCall, state: StateStore) -> PolicyResult:
    scope = tool_call.agent_id or "_global"
    count = state.count_events(self.policy_id, scope, window_seconds=3600.0)
    if count >= self.max:
        return PolicyResult.FAIL
    state.record_event(self.policy_id, scope)
    return PolicyResult.PASS
```

## Domain matching

Override `matches_domain` if your policy needs custom action matching:

```python
def matches_domain(self, action: str) -> bool:
    return "wire_transfer" in action.lower()
```

## Registering with the loader

Add your policy to the `_POLICY_MAP` in `policies/loader.py`:

```python
from mypackage import MyPolicy

_POLICY_MAP["myorg.my_policy"] = MyPolicy
```

## Using with Gate directly

```python
from diplomat_gate import Gate
from mypackage import MyPolicy

policy = MyPolicy(
    policy_id="myorg.my_policy",
    name="My Policy",
    domain="payment",
    severity="high",
    on_fail="STOP",
    threshold=500.0,
)

gate = Gate(policies=[policy])
verdict = gate.evaluate({"action": "charge_card", "some_param": 999})
```
