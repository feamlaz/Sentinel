"""Database layer — SQLite storage for targets and check results."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_DB_PATH = Path.home() / ".sentinel" / "sentinel.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    host        TEXT    NOT NULL,
    port        INTEGER DEFAULT NULL,
    check_type  TEXT    NOT NULL DEFAULT 'http',
    interval    INTEGER NOT NULL DEFAULT 300,
    active      INTEGER NOT NULL DEFAULT 1,
    tags        TEXT    DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id   INTEGER NOT NULL REFERENCES targets(id) ON DELETE CASCADE,
    status      TEXT    NOT NULL DEFAULT 'unknown',
    latency_ms  REAL    DEFAULT NULL,
    message     TEXT    DEFAULT '',
    details     TEXT    DEFAULT '{}',
    checked_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_results_target_id ON results(target_id);
CREATE INDEX IF NOT EXISTS idx_results_checked_at ON results(checked_at);
"""

CHECK_TYPES = ["http", "ssl", "dns", "port", "domain"]

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_DOWN = "down"
STATUS_UNKNOWN = "unknown"


@dataclass
class Target:
    id: Optional[int] = None
    name: str = ""
    host: str = ""
    port: Optional[int] = None
    check_type: str = "http"
    interval: int = 300
    active: bool = True
    tags: str = ""
    created_at: Optional[datetime] = None


@dataclass
class CheckResult:
    id: Optional[int] = None
    target_id: int = 0
    status: str = STATUS_UNKNOWN
    latency_ms: Optional[float] = None
    message: str = ""
    details: str = "{}"
    checked_at: Optional[datetime] = None

    @property
    def is_ok(self) -> bool:
        return self.status == STATUS_OK

    @property
    def is_warn(self) -> bool:
        return self.status == STATUS_WARN

    @property
    def is_down(self) -> bool:
        return self.status == STATUS_DOWN


def _row_to_target(row: sqlite3.Row) -> Target:
    return Target(
        id=row["id"],
        name=row["name"],
        host=row["host"],
        port=row["port"],
        check_type=row["check_type"],
        interval=row["interval"],
        active=bool(row["active"]),
        tags=row["tags"] or "",
        created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
    )


def _row_to_result(row: sqlite3.Row) -> CheckResult:
    return CheckResult(
        id=row["id"],
        target_id=row["target_id"],
        status=row["status"],
        latency_ms=row["latency_ms"],
        message=row["message"] or "",
        details=row["details"] or "{}",
        checked_at=datetime.fromisoformat(row["checked_at"]) if row["checked_at"] else None,
    )


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Targets CRUD ───────────────────────────────────────────────────

    def add_target(self, target: Target) -> Target:
        cur = self.conn.execute(
            """INSERT INTO targets (name, host, port, check_type, interval, active, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (target.name, target.host, target.port, target.check_type,
             target.interval, int(target.active), target.tags),
        )
        self.conn.commit()
        target.id = cur.lastrowid
        return target

    def get_target(self, target_id: int) -> Optional[Target]:
        row = self.conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
        return _row_to_target(row) if row else None

    def list_targets(self, active_only: bool = True) -> List[Target]:
        q = "SELECT * FROM targets"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY check_type, name"
        return [_row_to_target(r) for r in self.conn.execute(q).fetchall()]

    def update_target(self, target_id: int, **kwargs) -> Optional[Target]:
        existing = self.get_target(target_id)
        if not existing:
            return None
        fields = []
        values = []
        for key, val in kwargs.items():
            if key == "active" and isinstance(val, bool):
                val = int(val)
            fields.append("{} = ?".format(key))
            values.append(val)
        if not fields:
            return existing
        values.append(target_id)
        self.conn.execute(
            "UPDATE targets SET {} WHERE id = ?".format(", ".join(fields)), values
        )
        self.conn.commit()
        return self.get_target(target_id)

    def remove_target(self, target_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM targets WHERE id = ?", (target_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ── Results ────────────────────────────────────────────────────────

    def add_result(self, result: CheckResult) -> CheckResult:
        cur = self.conn.execute(
            """INSERT INTO results (target_id, status, latency_ms, message, details)
               VALUES (?, ?, ?, ?, ?)""",
            (result.target_id, result.status, result.latency_ms,
             result.message, result.details),
        )
        self.conn.commit()
        result.id = cur.lastrowid
        return result

    def get_latest_result(self, target_id: int) -> Optional[CheckResult]:
        row = self.conn.execute(
            "SELECT * FROM results WHERE target_id = ? ORDER BY checked_at DESC LIMIT 1",
            (target_id,),
        ).fetchone()
        return _row_to_result(row) if row else None

    def get_results(self, target_id: int, limit: int = 100) -> List[CheckResult]:
        rows = self.conn.execute(
            "SELECT * FROM results WHERE target_id = ? ORDER BY checked_at DESC LIMIT ?",
            (target_id, limit),
        ).fetchall()
        return [_row_to_result(r) for r in rows]

    def get_all_latest(self) -> Dict[int, CheckResult]:
        """Get latest result for each target."""
        results = {}
        rows = self.conn.execute(
            """SELECT r.* FROM results r
               INNER JOIN (
                   SELECT target_id, MAX(checked_at) as max_at
                   FROM results GROUP BY target_id
               ) latest ON r.target_id = latest.target_id AND r.checked_at = latest.max_at"""
        ).fetchall()
        for r in rows:
            result = _row_to_result(r)
            results[result.target_id] = result
        return results

    # ── Aggregations ───────────────────────────────────────────────────

    def get_uptime(self, target_id: int, hours: int = 24) -> float:
        """Uptime percentage for the last N hours."""
        total = self.conn.execute(
            "SELECT COUNT(*) FROM results WHERE target_id = ? AND checked_at >= datetime('now', ?)",
            (target_id, "-{} hours".format(hours)),
        ).fetchone()[0]
        if total == 0:
            return 100.0
        ok = self.conn.execute(
            "SELECT COUNT(*) FROM results WHERE target_id = ? AND status = ? AND checked_at >= datetime('now', ?)",
            (target_id, STATUS_OK, "-{} hours".format(hours)),
        ).fetchone()[0]
        return round((ok / total) * 100, 2)

    def get_avg_latency(self, target_id: int, hours: int = 24) -> Optional[float]:
        row = self.conn.execute(
            "SELECT AVG(latency_ms) FROM results WHERE target_id = ? AND latency_ms IS NOT NULL AND checked_at >= datetime('now', ?)",
            (target_id, "-{} hours".format(hours)),
        ).fetchone()
        val = row[0]
        return round(val, 1) if val is not None else None

    def cleanup_old(self, days: int = 30) -> int:
        cur = self.conn.execute(
            "DELETE FROM results WHERE checked_at < datetime('now', ?)",
            ("-{} days".format(days),),
        )
        self.conn.commit()
        return cur.rowcount
