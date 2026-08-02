"""Tests for dbpath.py."""

from dbpath import resolve_db_path


def test_defaults_to_local_relative_path(monkeypatch) -> None:
    monkeypatch.delenv("LQ_DB_PATH", raising=False)
    assert resolve_db_path() == "lithuanian_data.db"


def test_uses_lq_db_path_env_var_when_set(monkeypatch) -> None:
    monkeypatch.setenv("LQ_DB_PATH", "/data/lithuanian_data.db")
    assert resolve_db_path() == "/data/lithuanian_data.db"
