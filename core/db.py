"""
Phase 2: MySQL persistence layer.
Replaces the in-memory store from Phase 1.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import mysql.connector
from mysql.connector.pooling import MySQLConnectionPool

from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DATABASE,
)

logger = logging.getLogger(__name__)

_pool: Optional[MySQLConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool() -> MySQLConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = MySQLConnectionPool(
                    pool_name="job_platform",
                    pool_size=10,
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DATABASE,
                    autocommit=True,
                )
                logger.info("MySQL connection pool created")
    return _pool


def get_conn():
    return get_pool().get_connection()


# ─── Schema ───────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id            VARCHAR(36)  PRIMARY KEY,
    type          VARCHAR(50)  NOT NULL,
    status        VARCHAR(20)  NOT NULL DEFAULT 'QUEUED',
    priority      VARCHAR(10)  NOT NULL DEFAULT 'medium',
    payload       JSON,
    created_at    DATETIME(3)  NOT NULL,
    started_at    DATETIME(3),
    completed_at  DATETIME(3),
    retry_count   INT          NOT NULL DEFAULT 0,
    worker_id     VARCHAR(50),
    error         TEXT
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id       VARCHAR(50)  PRIMARY KEY,
    status          VARCHAR(20)  NOT NULL DEFAULT 'IDLE',
    last_heartbeat  DATETIME(3),
    jobs_processed  INT          NOT NULL DEFAULT 0,
    current_job_id  VARCHAR(36)
);

CREATE TABLE IF NOT EXISTS logs (
    id         BIGINT       AUTO_INCREMENT PRIMARY KEY,
    job_id     VARCHAR(36)  NOT NULL,
    message    TEXT         NOT NULL,
    timestamp  DATETIME(3)  NOT NULL
);
"""


def init_schema():
    """Create tables if they don't exist."""
    conn = get_conn()
    cursor = conn.cursor()
    for statement in SCHEMA_SQL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            cursor.execute(stmt)
    cursor.close()
    conn.close()
    logger.info("Database schema initialised")


# ─── Job operations ───────────────────────────────────────────────────────────

def _row_to_job(row, cursor) -> dict:
    cols = [d[0] for d in cursor.description]
    job = dict(zip(cols, row))
    # Convert datetime objects to ISO strings
    for field in ("created_at", "started_at", "completed_at"):
        if isinstance(job.get(field), datetime):
            job[field] = job[field].isoformat()
    # Parse JSON payload
    if isinstance(job.get("payload"), str):
        try:
            job["payload"] = json.loads(job["payload"])
        except Exception:
            pass
    return job


def save_job(job: dict) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO jobs (id, type, status, priority, payload, created_at,
                          started_at, completed_at, retry_count, worker_id, error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        job["id"], job["type"], job["status"], job["priority"],
        json.dumps(job.get("payload", {})),
        job["created_at"], job.get("started_at"), job.get("completed_at"),
        job.get("retry_count", 0), job.get("worker_id"), job.get("error"),
    ))
    cursor.close()
    conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
    row = cursor.fetchone()
    result = _row_to_job(row, cursor) if row else None
    cursor.close()
    conn.close()
    return result


def update_job(job_id: str, **fields) -> Optional[dict]:
    if not fields:
        return get_job(job_id)

    # Convert datetime strings back for MySQL
    set_clauses = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [job_id]

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE jobs SET {set_clauses} WHERE id = %s", values)
    cursor.close()
    conn.close()
    return get_job(job_id)


def list_jobs(status: Optional[str] = None) -> list[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM jobs WHERE status = %s ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    result = [_row_to_job(row, cursor) for row in rows]
    cursor.close()
    conn.close()
    return result


def delete_job(job_id: str) -> bool:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    affected = cursor.rowcount
    cursor.close()
    conn.close()
    return affected > 0


# ─── Worker operations ────────────────────────────────────────────────────────

def register_worker(worker_id: str) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO workers (worker_id, status, last_heartbeat, jobs_processed)
        VALUES (%s, 'IDLE', %s, 0)
        ON DUPLICATE KEY UPDATE
            status = 'IDLE',
            last_heartbeat = %s
    """, (worker_id, datetime.now(timezone.utc), datetime.now(timezone.utc)))
    cursor.close()
    conn.close()
    logger.info(f"Worker {worker_id} registered in DB")


def heartbeat(worker_id: str, status: str, current_job_id: Optional[str] = None) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE workers
        SET status = %s, last_heartbeat = %s, current_job_id = %s
        WHERE worker_id = %s
    """, (status, datetime.now(timezone.utc), current_job_id, worker_id))
    cursor.close()
    conn.close()


def increment_jobs_processed(worker_id: str) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE workers SET jobs_processed = jobs_processed + 1 WHERE worker_id = %s
    """, (worker_id,))
    cursor.close()
    conn.close()


def mark_worker_offline(worker_id: str) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE workers SET status = 'OFFLINE', current_job_id = NULL WHERE worker_id = %s
    """, (worker_id,))
    cursor.close()
    conn.close()


def list_workers() -> list[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers ORDER BY worker_id")
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    result = []
    for row in rows:
        w = dict(zip(cols, row))
        if isinstance(w.get("last_heartbeat"), datetime):
            w["last_heartbeat"] = w["last_heartbeat"].isoformat()
        result.append(w)
    cursor.close()
    conn.close()
    return result


# ─── Log operations ───────────────────────────────────────────────────────────

def add_log(job_id: str, message: str) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO logs (job_id, message, timestamp) VALUES (%s, %s, %s)
    """, (job_id, message, datetime.now(timezone.utc)))
    cursor.close()
    conn.close()


def get_logs(job_id: str) -> list[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM logs WHERE job_id = %s ORDER BY timestamp", (job_id,))
    rows = cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    result = []
    for row in rows:
        log = dict(zip(cols, row))
        if isinstance(log.get("timestamp"), datetime):
            log["timestamp"] = log["timestamp"].isoformat()
        result.append(log)
    cursor.close()
    conn.close()
    return result
