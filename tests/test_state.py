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


class TestRecordValue:
    def test_record_and_sum(self):
        s = StateStore()
        s.record_value("p1", "scope1", 100.5)
        s.record_value("p1", "scope1", 50.5)
        assert s.sum_values("p1", "scope1", 60.0) == 151.0

    def test_sum_isolated_by_scope(self):
        s = StateStore()
        s.record_value("p1", "scope1", 100)
        assert s.sum_values("p1", "scope2", 60.0) == 0.0

    def test_expired_values_purged(self):
        s = StateStore()
        s.record_value("p1", "s", 100, timestamp=time.time() - 200)
        s.record_value("p1", "s", 50)
        assert s.sum_values("p1", "s", 60.0) == 50.0

    def test_explicit_timestamp_in_window(self):
        s = StateStore()
        ts = time.time() - 30
        s.record_value("p1", "s", 25, timestamp=ts)
        assert s.sum_values("p1", "s", 60.0) == 25.0

    def test_empty_returns_zero(self):
        s = StateStore()
        assert s.sum_values("p1", "scope1", 60.0) == 0.0
