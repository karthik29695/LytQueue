"""
Phase 2/3: MySQL persistence layer using PyMySQL.
PyMySQL is pure Python — no C extensions, no Windows hangs.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import pymysql
import pymysql.cursors

from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DATABASE,
)

logger = logging.getLogger(__name__)


def get_conn():
    """Create a new PyMySQL connection. Always use in a with/try-finally block."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        autocommit=True,
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,  # returns dicts instead of tuples
    )


# ─── Schema ───────────────────────────────────────────────────────────────────

def init_schema():
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
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
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workers (
                    worker_id       VARCHAR(50)  PRIMARY KEY,
                    status          VARCHAR(20)  NOT NULL DEFAULT 'IDLE',
                    last_heartbeat  DATETIME(3),
                    jobs_processed  INT          NOT NULL DEFAULT 0,
                    current_job_id  VARCHAR(36)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id         BIGINT       AUTO_INCREMENT PRIMARY KEY,
                    job_id     VARCHAR(36)  NOT NULL,
                    message    TEXT         NOT NULL,
                    timestamp  DATETIME(3)  NOT NULL
                )
            """)
        logger.info("Database schema initialised")
    finally:
        conn.close()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fix_job(job: dict) -> dict:
    """Normalise a job row from DB — convert datetimes, parse JSON payload."""
    if not job:
        return job
    for field in ("created_at", "started_at", "completed_at"):
        if isinstance(job.get(field), datetime):
            job[field] = job[field].isoformat()
    if isinstance(job.get("payload"), str):
        try:
            job["payload"] = json.loads(job["payload"])
        except Exception:
            pass
    return job


# ─── Job operations ───────────────────────────────────────────────────────────

def save_job(job: dict) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
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
    finally:
        conn.close()


def get_job(job_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()
            return _fix_job(row) if row else None
    finally:
        conn.close()


def update_job(job_id: str, **fields) -> Optional[dict]:
    if not fields:
        return get_job(job_id)
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            set_clause = ", ".join(f"`{k}` = %s" for k in fields)
            values = list(fields.values()) + [job_id]
            cursor.execute(f"UPDATE jobs SET {set_clause} WHERE id = %s", values)
    finally:
        conn.close()
    return get_job(job_id)


def list_jobs(status: Optional[str] = None) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM jobs WHERE status = %s ORDER BY created_at DESC", (status,)
                )
            else:
                cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC")
            return [_fix_job(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def delete_job(job_id: str) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


# ─── Worker operations ────────────────────────────────────────────────────────

def register_worker(worker_id: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO workers (worker_id, status, last_heartbeat, jobs_processed)
                VALUES (%s, 'IDLE', %s, 0)
                ON DUPLICATE KEY UPDATE status = 'IDLE', last_heartbeat = %s
            """, (worker_id, datetime.now(timezone.utc), datetime.now(timezone.utc)))
        logger.info(f"Worker {worker_id} registered in DB")
    finally:
        conn.close()


def heartbeat(worker_id: str, status: str, current_job_id: Optional[str] = None) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE workers
                SET status = %s, last_heartbeat = %s, current_job_id = %s
                WHERE worker_id = %s
            """, (status, datetime.now(timezone.utc), current_job_id, worker_id))
    finally:
        conn.close()


def increment_jobs_processed(worker_id: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE workers SET jobs_processed = jobs_processed + 1 WHERE worker_id = %s",
                (worker_id,)
            )
    finally:
        conn.close()


def mark_worker_offline(worker_id: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE workers SET status = 'OFFLINE', current_job_id = NULL WHERE worker_id = %s",
                (worker_id,)
            )
    finally:
        conn.close()


def list_workers() -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM workers ORDER BY worker_id")
            rows = cursor.fetchall()
            for w in rows:
                if isinstance(w.get("last_heartbeat"), datetime):
                    w["last_heartbeat"] = w["last_heartbeat"].isoformat()
            return rows
    finally:
        conn.close()


# ─── Log operations ───────────────────────────────────────────────────────────

def add_log(job_id: str, message: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO logs (job_id, message, timestamp) VALUES (%s, %s, %s)",
                (job_id, message, datetime.now(timezone.utc))
            )
    finally:
        conn.close()


def get_logs(job_id: str) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM logs WHERE job_id = %s ORDER BY timestamp", (job_id,)
            )
            rows = cursor.fetchall()
            for log in rows:
                if isinstance(log.get("timestamp"), datetime):
                    log["timestamp"] = log["timestamp"].isoformat()
            return rows
    finally:
        conn.close()
