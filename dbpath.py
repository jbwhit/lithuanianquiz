"""Resolves the SQLite DB path — a Railway volume in production, a local file in dev."""

import os


def resolve_db_path() -> str:
    """Return the SQLite DB path.

    Defaults to the relative `lithuanian_data.db` (repo root — used for
    local dev and tests). In production, `LQ_DB_PATH` points at a Railway
    volume mount instead: the container's own filesystem doesn't survive
    restarts or redeploys, so anything not on a volume is lost.
    """
    return os.environ.get("LQ_DB_PATH", "lithuanian_data.db")
