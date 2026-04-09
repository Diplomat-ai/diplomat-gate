"""Tests for the in-memory state store."""

import time

from diplomat_gate.state import StateStore


class TestStateStore:
    def test_record_and_count(self):
        s = StateStore()
        s.record_event("p1", "scope1")
        s.record_event("p1", "scope1")
        assert s.count_events("p1", "scope1", 60.0) == 2

    def test_different_scopes_isolated(self):
        s = StateStore()
        s.record_event("p1", "scope1")
        assert s.count_events("p1", "scope2", 60.0) == 0

    def test_expired_events_not_counted(self):
        s = StateStore()
        # Manually insert an old timestamp
        key = s._key("p1", "scope1")
        s._data[key].timestamps.append(time.time() - 200)
        assert s.count_events("p1", "scope1", 60.0) == 0

    def test_find_duplicate_false_initially(self):
        s = StateStore()
        assert not s.find_duplicate("p1", "scope1", 60.0)

    def test_find_duplicate_true_after_record(self):
        s = StateStore()
        s.record_event("p1", "scope1")
        assert s.find_duplicate("p1", "scope1", 60.0)

    def test_last_event_time_none(self):
        s = StateStore()
        assert s.last_event_time("p1", "scope1") is None

    def test_last_event_time_set(self):
        s = StateStore()
        before = time.time()
        s.record_event("p1", "scope1")
        after = time.time()
        t = s.last_event_time("p1", "scope1")
        assert before <= t <= after

    def test_clear(self):
        s = StateStore()
        s.record_event("p1", "scope1")
        s.clear()
        assert s.count_events("p1", "scope1", 60.0) == 0
