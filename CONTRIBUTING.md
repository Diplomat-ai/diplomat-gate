# Contributing to diplomat-gate

Thanks for your interest. diplomat-gate is a solo-maintained project — I read
every issue and every PR.

## Before contributing

- For a **bug fix** or a **good first issue**: open the issue first if one
  doesn't exist, describe the problem in 3-5 lines, then say you're working
  on it.
- For a **new policy** or **new adapter**: open a discussion issue first.
  Not every idea fits the “deterministic, no LLM, zero mandatory deps”
  constraint.
- For **larger changes** (new subsystem, API break): open a discussion and
  wait for a maintainer response before coding.

## Local setup

```bash
git clone https://github.com/Diplomat-ai/diplomat-gate.git
cd diplomat-gate
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[all]"
pip install ruff pytest
```

## Running tests and checks

```bash
# All tests
pytest

# Lint + format check
ruff check .
ruff format --check .

# Auto-fix imports
ruff check . --select I001 --fix

# Full release gate (slow)
python scripts/validate_release.py
```

## Coding style

- Python ≥ 3.10 syntax, no newer
- No mandatory new dependencies. Everything new goes in optional extras
  (`[yaml]`, `[rich]`, etc.)
- Type hints mandatory on public APIs
- Docstrings in Google style for public classes
- Deterministic behavior: no randomness, no time-based choices, no LLM calls
  in the evaluation path

## Writing a new policy

1. Subclass `diplomat_gate.policies.base.Policy`
2. Register its ID in `diplomat_gate.policies.loader._POLICY_MAP`
3. Add a test in `tests/test_policies_<domain>.py`
4. Add a one-line row in the corresponding table of `README.md`
5. Update `docs/writing-policies.md` if the policy introduces a new pattern

## PRs

- Branch from `main`
- One logical change per PR. A PR that touches 5 unrelated files gets split
  or rejected.
- CI must be green before review
- Squash-merge is the default

## Security vulnerabilities

Do **not** file public issues. See [`SECURITY.md`](SECURITY.md).

## License

By contributing, you agree your contributions are licensed under Apache 2.0.
