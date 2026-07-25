from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class InvestigationStore:
    """Durable local investigation ledger.

    Connections are intentionally short-lived so the store is safe to use from
    the threaded HTTP server without sharing SQLite connection objects.
    """

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _session(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._session() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL
                        CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
                    mode TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    finding_json TEXT,
                    finding_hash TEXT,
                    artifact_dir TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS investigations_created_at
                ON investigations(created_at DESC)
                """
            )

    def start(self, run_id: str, mode: str, request: dict[str, Any]) -> None:
        now = utc_now()
        with self._session() as connection:
            connection.execute(
                """
                INSERT INTO investigations(
                    id, status, mode, request_json, created_at, updated_at
                ) VALUES (?, 'RUNNING', ?, ?, ?, ?)
                """,
                (run_id, mode, json.dumps(request, sort_keys=True), now, now),
            )

    def complete(
        self,
        run_id: str,
        finding: dict[str, Any],
        finding_hash: str,
        artifact_dir: Path,
    ) -> None:
        with self._session() as connection:
            cursor = connection.execute(
                """
                UPDATE investigations
                SET status = 'COMPLETED',
                    finding_json = ?,
                    finding_hash = ?,
                    artifact_dir = ?,
                    error = NULL,
                    updated_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (
                    json.dumps(finding, sort_keys=True),
                    finding_hash,
                    str(artifact_dir.resolve()),
                    utc_now(),
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"investigation {run_id} is not running")

    def fail(self, run_id: str, error: str) -> None:
        with self._session() as connection:
            connection.execute(
                """
                UPDATE investigations
                SET status = 'FAILED', error = ?, updated_at = ?
                WHERE id = ? AND status = 'RUNNING'
                """,
                (error[:2000], utc_now(), run_id),
            )

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._session() as connection:
            row = connection.execute(
                "SELECT * FROM investigations WHERE id = ?", (run_id,)
            ).fetchone()
        return self._decode(row) if row else None

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT * FROM investigations
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._decode(row) for row in rows]

    def ready(self) -> tuple[bool, str]:
        try:
            with self._session() as connection:
                result = connection.execute("PRAGMA quick_check").fetchone()[0]
                connection.execute("SELECT 1").fetchone()
            return result == "ok", result
        except sqlite3.Error as exc:
            return False, str(exc)

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        record = dict(row)
        record["request"] = json.loads(record.pop("request_json"))
        finding = record.pop("finding_json")
        record["finding"] = json.loads(finding) if finding else None
        return record
