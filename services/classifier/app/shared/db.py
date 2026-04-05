from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.shared.config import settings


@dataclass
class RowCase:
    case_id: str
    status: str
    created_at: str
    updated_at: str
    payload_json: str


class SQLiteRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = Path(db_path or settings.sqlite_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analysis_jobs (
                    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_runs (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    analyzer TEXT NOT NULL,
                    model_name TEXT,
                    score REAL,
                    confidence REAL,
                    debug_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evidence_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reports (
                    case_id TEXT PRIMARY KEY,
                    report_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT,
                    level TEXT NOT NULL,
                    event TEXT NOT NULL,
                    detail_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    note TEXT,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rate_limit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    ts_epoch INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_rate_limit_ip_endpoint_ts
                    ON rate_limit_events(ip, endpoint, ts_epoch);
                """
            )

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_case(self, case_id: str, payload: dict[str, Any], status: str = "accepted") -> None:
        now = self.now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO cases(case_id, status, created_at, updated_at, payload_json)
                VALUES(?,?,?,?,?)
                ON CONFLICT(case_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    payload_json=excluded.payload_json
                """,
                (case_id, status, now, now, json.dumps(payload)),
            )

    def update_case_status(self, case_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE cases SET status=?, updated_at=? WHERE case_id=?",
                (status, self.now_iso(), case_id),
            )

    def get_case(self, case_id: str) -> RowCase | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            if not row:
                return None
            return RowCase(
                case_id=row["case_id"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                payload_json=row["payload_json"],
            )

    def upsert_report(self, case_id: str, report: dict[str, Any]) -> None:
        now = self.now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO reports(case_id, report_json, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(case_id) DO UPDATE SET
                    report_json=excluded.report_json,
                    updated_at=excluded.updated_at
                """,
                (case_id, json.dumps(report), now),
            )

    def get_report(self, case_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT report_json FROM reports WHERE case_id=?", (case_id,)).fetchone()
            if not row:
                return None
            return json.loads(row["report_json"])

    def insert_job_event(self, case_id: str, status: str, stage: str, message: str | None = None) -> None:
        now = self.now_iso()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO analysis_jobs(case_id, status, stage, message, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (case_id, status, stage, message, now, now),
            )

    def insert_model_run(
        self,
        case_id: str,
        analyzer: str,
        model_name: str,
        score: float,
        confidence: float,
        debug: dict[str, Any],
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO model_runs(case_id, analyzer, model_name, score, confidence, debug_json, created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    case_id,
                    analyzer,
                    model_name,
                    score,
                    confidence,
                    json.dumps(debug),
                    self.now_iso(),
                ),
            )

    def insert_evidence(self, case_id: str, evidence: list[dict[str, Any]]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO evidence_summaries(case_id, evidence_json, created_at) VALUES(?,?,?)",
                (case_id, json.dumps(evidence), self.now_iso()),
            )

    def insert_audit_log(
        self,
        event: str,
        level: str = "info",
        case_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_logs(case_id, level, event, detail_json, created_at) VALUES(?,?,?,?,?)",
                (case_id, level, event, json.dumps(detail or {}), self.now_iso()),
            )

    def add_feedback(self, case_id: str, label: str, note: str | None, metadata: dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO feedback(case_id, label, note, metadata_json, created_at) VALUES(?,?,?,?,?)",
                (case_id, label, note, json.dumps(metadata), self.now_iso()),
            )

    def record_rate_limit_event(self, ip: str, endpoint: str, ts_epoch: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO rate_limit_events(ip, endpoint, ts_epoch) VALUES(?,?,?)",
                (ip, endpoint, ts_epoch),
            )

    def count_recent_rate_limit_events(self, ip: str, endpoint: str, cutoff_epoch: int) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM rate_limit_events WHERE ip=? AND endpoint=? AND ts_epoch>=?",
                (ip, endpoint, cutoff_epoch),
            ).fetchone()
            return int(row["c"] if row else 0)

    def prune_rate_limit_events(self, cutoff_epoch: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM rate_limit_events WHERE ts_epoch<?", (cutoff_epoch,))
