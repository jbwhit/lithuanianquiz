"""Resolves the SQLite DB path — a Railway volume in production, a local file in dev."""

import os
import shutil


def resolve_db_path() -> str:
    """Return the SQLite DB path.

    Defaults to the relative `lithuanian_data.db` (repo root — used for
    local dev and tests). In production, `LQ_DB_PATH` points at a Railway
    volume mount instead: the container's own filesystem doesn't survive
    restarts or redeploys, so anything not on a volume is lost.
    """
    return os.environ.get("LQ_DB_PATH", "lithuanian_data.db")


def ensure_db_seeded(path: str, source: str = "lithuanian_data.db") -> None:
    """Copy `source` to `path` if `path` doesn't already exist.

    A fresh Railway volume starts empty, but the app needs the bundled
    reference data (the `numbers` table) to boot. Never overwrites an
    existing file at `path`, so accumulated user data already on the
    volume survives every redeploy.
    """
    if os.path.abspath(path) == os.path.abspath(source):
        return
    if os.path.exists(path):
        return
    shutil.copy(source, path)
