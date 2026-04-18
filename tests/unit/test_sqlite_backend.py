"""Tests for the Protocol SQLite persistence backend.

Mirrors the governance/advisor pattern: same behavioural properties,
different storage engine. Does NOT require Windows; SQLite ships with CPython.

Covers:
  - write_event / read_events round-trip (ProtocolEvent objects)
  - query_events alias
  - verify_event raises on missing/wrong HMAC
  - append-only enforcement via triggers
  - category filtering via event_id range
  - Corrupted data_json rows skipped silently
  - Factory (get_backend / default_backend_name / env var selection)
  - count_events, in-memory store, post-close write raises
  - EventViewerBackend delegates and returns []
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from persistence import SQLiteBackend, default_backend_name, get_backend
from persistence.event_viewer_backend import EventViewerBackend
from persistence.sqlite_backend import SQLiteBackendError
from schema.event import ProtocolCategory, ProtocolEvent

# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

_CATEGORIES = list(ProtocolCategory)


def _make_event(
    category: ProtocolCategory = ProtocolCategory.DECLARATION,
    event_id: int = 7000,
    agent_id: str = "pytest-agent",
    message: str = "test event",
) -> ProtocolEvent:
    return ProtocolEvent(
        message=message,
        category=category,
        event_id=event_id,
        agent_id=agent_id,
        declaration_id=str(uuid.uuid4()),
        data={"key": "value"},
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteBackend:
    backend = SQLiteBackend(tmp_path / "events.db")
    yield backend
    backend.close()


# ------------------------------------------------------------------ #
# Basic write / read                                                   #
# ------------------------------------------------------------------ #


class TestWriteAndRead:
    def test_round_trip(self, store: SQLiteBackend) -> None:
        event = _make_event(message="round-trip test")
        store.write_event(event)

        rows = store.read_events(max_records=10)
        assert len(rows) == 1
        recovered = rows[0]
        assert recovered.message == "round-trip test"
        assert recovered.category == event.category
        assert recovered.event_id == event.event_id
        assert recovered.agent_id == event.agent_id

    def test_read_returns_newest_first(self, store: SQLiteBackend) -> None:
        for i, cat in enumerate(_CATEGORIES):
            store.write_event(_make_event(category=cat, event_id=7000 + i * 100))
        rows = store.read_events(max_records=10)
        assert rows[0].event_id > rows[-1].event_id

    def test_max_records_caps_result(self, store: SQLiteBackend) -> None:
        for i in range(5):
            store.write_event(_make_event(event_id=7000 + i))
        assert len(store.read_events(max_records=3)) == 3

    def test_empty_store_returns_empty_list(self, store: SQLiteBackend) -> None:
        assert store.read_events() == []

    def test_query_events_alias(self, store: SQLiteBackend) -> None:
        store.write_event(_make_event())
        assert len(store.query_events()) == 1

    def test_max_records_zero_returns_empty(self, store: SQLiteBackend) -> None:
        store.write_event(_make_event())
        assert store.read_events(max_records=0) == []

    def test_data_preserved(self, store: SQLiteBackend) -> None:
        event = _make_event()
        event2 = event.model_copy(update={"data": {"foo": "bar", "n": 42}})
        store.write_event(event2)
        recovered = store.read_events()[0]
        assert recovered.data == {"foo": "bar", "n": 42}


# ------------------------------------------------------------------ #
# Category filtering                                                   #
# ------------------------------------------------------------------ #


class TestCategoryFilter:
    def test_filter_by_category_returns_only_matching(
        self, store: SQLiteBackend
    ) -> None:
        store.write_event(_make_event(ProtocolCategory.DECLARATION, event_id=7000))
        store.write_event(_make_event(ProtocolCategory.VALIDATION, event_id=7100))
        store.write_event(_make_event(ProtocolCategory.DISPOSITION, event_id=7200))

        decl_rows = store.read_events(category=ProtocolCategory.DECLARATION)
        assert len(decl_rows) == 1
        assert decl_rows[0].category == ProtocolCategory.DECLARATION

    def test_no_category_returns_all(self, store: SQLiteBackend) -> None:
        for cat, eid in [
            (ProtocolCategory.DECLARATION, 7000),
            (ProtocolCategory.VALIDATION, 7100),
        ]:
            store.write_event(_make_event(cat, event_id=eid))
        assert len(store.read_events()) == 2

    def test_category_with_no_matches_returns_empty(
        self, store: SQLiteBackend
    ) -> None:
        store.write_event(_make_event(ProtocolCategory.DECLARATION, event_id=7000))
        rows = store.read_events(category=ProtocolCategory.SIGNING)
        assert rows == []


# ------------------------------------------------------------------ #
# HMAC preservation                                                    #
# ------------------------------------------------------------------ #


class TestHMACPreservation:
    def test_hmac_none_stored_and_recovered(self, store: SQLiteBackend) -> None:
        event = _make_event()
        assert event.hmac is None
        store.write_event(event)
        recovered = store.read_events()[0]
        assert recovered.hmac is None

    def test_hmac_value_preserved(self, store: SQLiteBackend) -> None:
        event = _make_event()
        event_with_hmac = event.model_copy(update={"hmac": "deadbeef" * 8})
        store.write_event(event_with_hmac)
        recovered = store.read_events()[0]
        assert recovered.hmac == "deadbeef" * 8

    def test_verify_event_raises_on_missing_hmac(
        self, store: SQLiteBackend
    ) -> None:
        event = _make_event()
        assert event.hmac is None
        with pytest.raises(ValueError, match="no hmac"):
            store.verify_event(event, b"\x00" * 32)

    def test_verify_event_raises_on_wrong_key(self, store: SQLiteBackend) -> None:
        import hashlib
        import hmac as _hmac

        event = _make_event()
        key = b"\x01" * 32
        payload = event.signing_payload()
        good_hmac = _hmac.new(key, payload, hashlib.sha256).hexdigest()
        signed = event.model_copy(update={"hmac": good_hmac})

        with pytest.raises(ValueError, match="HMAC mismatch"):
            store.verify_event(signed, b"\x00" * 32)

    def test_verify_event_passes_for_correct_key(
        self, store: SQLiteBackend
    ) -> None:
        import hashlib
        import hmac as _hmac

        key = b"\x01" * 32
        event = _make_event()
        payload = event.signing_payload()
        good_hmac = _hmac.new(key, payload, hashlib.sha256).hexdigest()
        signed = event.model_copy(update={"hmac": good_hmac})

        assert store.verify_event(signed, key) is True


# ------------------------------------------------------------------ #
# Corrupted rows skipped                                               #
# ------------------------------------------------------------------ #


class TestCorruptedRowsSkipped:
    def test_bad_data_json_skipped(self, store: SQLiteBackend) -> None:
        store.write_event(_make_event())
        raw = sqlite3.connect(store.path)
        try:
            # Insert a corrupt row directly (bypassing the Python layer).
            raw.execute(
                "INSERT INTO events "
                "(category, event_id, agent_id, message, data_json, hmac, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    "DECLARATION",
                    7000,
                    "corrupt-agent",
                    "msg",
                    "NOT_JSON{{{{",
                    None,
                    "2024-01-01T00:00:00+00:00",
                ),
            )
            raw.commit()
        finally:
            raw.close()

        rows = store.read_events()
        assert len(rows) == 1  # corrupt row skipped; valid row returned


# ------------------------------------------------------------------ #
# Append-only                                                          #
# ------------------------------------------------------------------ #


class TestAppendOnly:
    def test_update_is_blocked(self, store: SQLiteBackend) -> None:
        store.write_event(_make_event())
        raw = sqlite3.connect(store.path)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                raw.execute("UPDATE events SET message = 'mutated'")
        finally:
            raw.close()

    def test_delete_is_blocked(self, store: SQLiteBackend) -> None:
        store.write_event(_make_event())
        raw = sqlite3.connect(store.path)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="append-only"):
                raw.execute("DELETE FROM events")
        finally:
            raw.close()


# ------------------------------------------------------------------ #
# Factory                                                              #
# ------------------------------------------------------------------ #


class TestFactory:
    def test_explicit_sqlite_backend(self, tmp_path: Path) -> None:
        b = get_backend(backend="sqlite", sqlite_path=tmp_path / "f.db")
        try:
            assert isinstance(b, SQLiteBackend)
        finally:
            b.close()

    def test_env_var_selects_sqlite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        monkeypatch.setenv("PROTOCOL_SQLITE_PATH", str(tmp_path / "env.db"))
        b = get_backend()
        try:
            assert isinstance(b, SQLiteBackend)
            assert b.path.endswith("env.db")
        finally:
            b.close()

    def test_unknown_backend_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown PERSISTENCE_BACKEND"):
            get_backend(backend="kafka")

    def test_default_backend_name_on_non_windows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
        monkeypatch.setattr("sys.platform", "linux")
        assert default_backend_name() == "sqlite"

    def test_env_var_overrides_platform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PERSISTENCE_BACKEND", "sqlite")
        assert default_backend_name() == "sqlite"


# ------------------------------------------------------------------ #
# Count, path, in-memory                                              #
# ------------------------------------------------------------------ #


class TestCountAndPath:
    def test_count_events_tracks_inserts(self, store: SQLiteBackend) -> None:
        assert store.count_events() == 0
        for cat, eid in [
            (ProtocolCategory.DECLARATION, 7000),
            (ProtocolCategory.VALIDATION, 7100),
            (ProtocolCategory.DISPOSITION, 7200),
        ]:
            store.write_event(_make_event(cat, event_id=eid))
        assert store.count_events() == 3

    def test_in_memory_store(self) -> None:
        b = SQLiteBackend(":memory:")
        try:
            b.write_event(_make_event())
            assert b.count_events() == 1
        finally:
            b.close()

    def test_path_property(self, tmp_path: Path) -> None:
        p = tmp_path / "proto.db"
        b = SQLiteBackend(p)
        try:
            assert b.path == str(p)
        finally:
            b.close()


# ------------------------------------------------------------------ #
# Write errors                                                         #
# ------------------------------------------------------------------ #


class TestWriteErrors:
    def test_write_after_close_raises(self, tmp_path: Path) -> None:
        b = SQLiteBackend(tmp_path / "closed.db")
        b.close()
        with pytest.raises(SQLiteBackendError):
            b.write_event(_make_event())


# ------------------------------------------------------------------ #
# EventViewerBackend interface                                         #
# ------------------------------------------------------------------ #


class TestEventViewerBackendInterface:
    def test_delegates_to_event_viewer_writer(self) -> None:
        mock_write = MagicMock()
        mock_read = MagicMock(return_value=[])
        with patch.dict(
            "sys.modules",
            {
                "event_viewer": MagicMock(),
                "event_viewer.writer": MagicMock(
                    write_event=mock_write, read_events=mock_read
                ),
            },
        ):
            b = EventViewerBackend()
            event = _make_event()
            b.write_event(event)
            mock_write.assert_called_once_with(event)

    def test_read_events_delegates(self) -> None:
        mock_write = MagicMock()
        mock_read = MagicMock(return_value=[])
        with patch.dict(
            "sys.modules",
            {
                "event_viewer": MagicMock(),
                "event_viewer.writer": MagicMock(
                    write_event=mock_write, read_events=mock_read
                ),
            },
        ):
            b = EventViewerBackend()
            result = b.read_events(max_records=5, category=ProtocolCategory.DECLARATION)
            mock_read.assert_called_once_with(
                max_records=5, category=ProtocolCategory.DECLARATION
            )
            assert result == []
