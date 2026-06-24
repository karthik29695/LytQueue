"""
Watchdog: monitors worker heartbeats.
If a worker goes silent for > HEARTBEAT_TIMEOUT seconds:
  1. Marks it OFFLINE in MySQL
  2. Finds any RUNNING jobs assigned to it
  3. Re-queues those jobs for another worker
"""
import time
import logging
import threading
from datetime import datetime, timezone, timedelta

from config import QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW
from core import queue, db

logger = logging.getLogger("watchdog")

HEARTBEAT_TIMEOUT = 15
WATCHDOG_INTERVAL = 5

PRIORITY_QUEUE_MAP = {
    "high":   QUEUE_HIGH,
    "medium": QUEUE_MEDIUM,
    "low":    QUEUE_LOW,
}

_watchdog_thread = None
_running = False


def _check_workers():
    workers = db.list_workers()
    now = datetime.now(timezone.utc)

    for worker in workers:
        if worker["status"] == "OFFLINE":
            continue
        last_hb = worker.get("last_heartbeat")
        if not last_hb:
            continue
        try:
            hb_time = datetime.fromisoformat(last_hb)
            if hb_time.tzinfo is None:
                hb_time = hb_time.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        age = (now - hb_time).total_seconds()
        if age > HEARTBEAT_TIMEOUT:
            worker_id = worker["worker_id"]
            logger.warning(f"Worker {worker_id} heartbeat is {age:.0f}s old — marking OFFLINE")
            db.mark_worker_offline(worker_id)
            _recover_jobs(worker_id)


def _recover_jobs(worker_id: str):
    conn = db.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM jobs WHERE worker_id = %s AND status = 'RUNNING'",
                (worker_id,)
            )
            stuck_jobs = cursor.fetchall()
    finally:
        conn.close()

    for job in stuck_jobs:
        job_id   = job["id"]
        priority = job.get("priority", "medium")
        q_name   = PRIORITY_QUEUE_MAP.get(priority, QUEUE_MEDIUM)

        logger.warning(f"Recovering stuck job {job_id} from dead worker {worker_id}")
        updated = db.update_job(job_id, status="QUEUED", worker_id=None, started_at=None)
        queue.push_job(q_name, updated)
        db.add_log(job_id, f"Recovered: worker {worker_id} went OFFLINE, re-queued to {q_name}")
        logger.info(f"Job {job_id} re-queued to {q_name}")


def _watchdog_loop():
    global _running
    logger.info("Watchdog started")
    while _running:
        try:
            _check_workers()
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        time.sleep(WATCHDOG_INTERVAL)
    logger.info("Watchdog stopped")


def start_watchdog():
    global _watchdog_thread, _running
    if _watchdog_thread and _watchdog_thread.is_alive():
        return
    _running = True
    _watchdog_thread = threading.Thread(target=_watchdog_loop, daemon=True, name="watchdog")
    _watchdog_thread.start()


def stop_watchdog():
    global _running
    _running = False
