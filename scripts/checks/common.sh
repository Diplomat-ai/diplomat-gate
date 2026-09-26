#!/usr/bin/env bash
set -euo pipefail
assert_eq() {
  local actual="$1" expected="$2" msg="$3"
  if [ "$actual" != "$expected" ]; then
    echo "FAIL: $msg — got '$actual', expected '$expected'"
    exit 1
  fi
}
