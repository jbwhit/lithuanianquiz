"""Tests for dbpath.py."""

from dbpath import resolve_db_path


def test_defaults_to_local_relative_path(monkeypatch) -> None:
    monkeypatch.delenv("LQ_DB_PATH", raising=False)
    assert resolve_db_path() == "lithuanian_data.db"


def test_uses_lq_db_path_env_var_when_set(monkeypatch) -> None:
    monkeypatch.setenv("LQ_DB_PATH", "/data/lithuanian_data.db")
    assert resolve_db_path() == "/data/lithuanian_data.db"


def test_ensure_db_seeded_copies_source_when_target_missing(tmp_path) -> None:
    from dbpath import ensure_db_seeded

    source = tmp_path / "source.db"
    source.write_bytes(b"seed-data")
    target = tmp_path / "sub" / "target.db"
    target.parent.mkdir()

    ensure_db_seeded(str(target), source=str(source))

    assert target.read_bytes() == b"seed-data"


def test_ensure_db_seeded_does_not_overwrite_existing_target(tmp_path) -> None:
    from dbpath import ensure_db_seeded

    source = tmp_path / "source.db"
    source.write_bytes(b"seed-data")
    target = tmp_path / "target.db"
    target.write_bytes(b"real-user-data")

    ensure_db_seeded(str(target), source=str(source))

    assert target.read_bytes() == b"real-user-data"


def test_ensure_db_seeded_is_a_noop_when_path_equals_source(tmp_path) -> None:
    from dbpath import ensure_db_seeded

    source = tmp_path / "same.db"
    source.write_bytes(b"local-dev-data")

    ensure_db_seeded(str(source), source=str(source))

    assert source.read_bytes() == b"local-dev-data"
