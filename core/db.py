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
                                  started_at, completed_at, retry_count, worker_id, error,
                                  run_at, schedule_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                job["id"], job["type"], job["status"], job["priority"],
                json.dumps(job.get("payload", {})),
                job["created_at"], job.get("started_at"), job.get("completed_at"),
                job.get("retry_count", 0), job.get("worker_id"), job.get("error"),
                job.get("run_at"), job.get("schedule_id"),
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


# ─── Scheduling schema (Phase 5) ──────────────────────────────────────────────

def init_schedule_schema():
    """Add scheduling columns and tables. Safe to run multiple times."""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            # Add run_at to jobs if not exists
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME   = 'jobs'
                  AND COLUMN_NAME  = 'run_at'
            """)
            if cursor.fetchone()["cnt"] == 0:
                cursor.execute("ALTER TABLE jobs ADD COLUMN run_at DATETIME(3) NULL")
                cursor.execute("ALTER TABLE jobs ADD COLUMN schedule_id VARCHAR(36) NULL")
                logger.info("Added run_at and schedule_id columns to jobs")

            # Recurring schedules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id                VARCHAR(36)   PRIMARY KEY,
                    name              VARCHAR(100)  NOT NULL,
                    job_type          VARCHAR(50)   NOT NULL,
                    priority          VARCHAR(10)   NOT NULL DEFAULT 'medium',
                    payload           JSON,
                    cron_expression   VARCHAR(100)  NULL,
                    interval_seconds  INT           NULL,
                    next_run_at       DATETIME(3)   NOT NULL,
                    last_run_at       DATETIME(3)   NULL,
                    is_active         TINYINT(1)    NOT NULL DEFAULT 1,
                    created_at        DATETIME(3)   NOT NULL,
                    run_count         INT           NOT NULL DEFAULT 0
                )
            """)
        logger.info("Schedule schema initialised")
    finally:
        conn.close()


# ─── One-time scheduled job queries ──────────────────────────────────────────

def get_due_scheduled_jobs() -> list[dict]:
    """Return jobs that are SCHEDULED and whose run_at has passed."""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM jobs
                WHERE status = 'SCHEDULED'
                  AND run_at <= NOW()
                ORDER BY run_at ASC
            """)
            return [_fix_job(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def list_scheduled_jobs() -> list[dict]:
    """Return all jobs still waiting to be scheduled (run_at in future)."""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM jobs
                WHERE status = 'SCHEDULED'
                ORDER BY run_at ASC
            """)
            return [_fix_job(r) for r in cursor.fetchall()]
    finally:
        conn.close()


# ─── Recurring schedule queries ───────────────────────────────────────────────

def save_schedule(schedule: dict) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO schedules
                  (id, name, job_type, priority, payload, cron_expression,
                   interval_seconds, next_run_at, last_run_at, is_active, created_at, run_count)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                schedule["id"], schedule["name"], schedule["job_type"],
                schedule["priority"], json.dumps(schedule.get("payload", {})),
                schedule.get("cron_expression"), schedule.get("interval_seconds"),
                schedule["next_run_at"], schedule.get("last_run_at"),
                1, schedule["created_at"], 0,
            ))
    finally:
        conn.close()


def get_schedule(schedule_id: str) -> Optional[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM schedules WHERE id = %s", (schedule_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return _fix_schedule(row)
    finally:
        conn.close()


def list_schedules() -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM schedules ORDER BY created_at DESC")
            return [_fix_schedule(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_due_schedules() -> list[dict]:
    """Return active recurring schedules whose next_run_at has passed."""
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM schedules
                WHERE is_active = 1
                  AND next_run_at <= NOW()
                ORDER BY next_run_at ASC
            """)
            return [_fix_schedule(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def update_schedule(schedule_id: str, **fields) -> Optional[dict]:
    if not fields:
        return get_schedule(schedule_id)
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            set_clause = ", ".join(f"`{k}` = %s" for k in fields)
            values = list(fields.values()) + [schedule_id]
            cursor.execute(f"UPDATE schedules SET {set_clause} WHERE id = %s", values)
    finally:
        conn.close()
    return get_schedule(schedule_id)


def delete_schedule(schedule_id: str) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def get_jobs_by_schedule(schedule_id: str, limit: int = 20) -> list[dict]:
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM jobs WHERE schedule_id = %s
                ORDER BY created_at DESC LIMIT %s
            """, (schedule_id, limit))
            return [_fix_job(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def _fix_schedule(s: dict) -> dict:
    if not s:
        return s
    for field in ("next_run_at", "last_run_at", "created_at"):
        if isinstance(s.get(field), datetime):
            s[field] = s[field].isoformat()
    if isinstance(s.get("payload"), str):
        try:
            s["payload"] = json.loads(s["payload"])
        except Exception:
            pass
    return s
