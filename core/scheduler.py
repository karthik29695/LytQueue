"""
Scheduler: background thread that fires scheduled jobs.

Every SCHEDULER_INTERVAL seconds:
  1. One-time jobs  — find SCHEDULED jobs with run_at <= NOW(), push to queue
  2. Recurring jobs — find active schedules with next_run_at <= NOW(),
                      create a job, push to queue, compute next_run_at
"""
import uuid
import logging
import threading
import time
from datetime import datetime, timezone

from croniter import croniter

from config import QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW
from core import queue, db

logger = logging.getLogger("scheduler")

SCHEDULER_INTERVAL = 5  # seconds

PRIORITY_QUEUE_MAP = {
    "high":   QUEUE_HIGH,
    "medium": QUEUE_MEDIUM,
    "low":    QUEUE_LOW,
}

_scheduler_thread = None
_running = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_str() -> str:
    return _utcnow().isoformat()


# ── One-time job firing ───────────────────────────────────────────────────────

def _fire_scheduled_jobs():
    due = db.get_due_scheduled_jobs()
    for job in due:
        job_id    = job["id"]
        priority  = job.get("priority", "medium")
        q_name    = PRIORITY_QUEUE_MAP.get(priority, QUEUE_MEDIUM)

        db.update_job(job_id, status="QUEUED")
        job["status"] = "QUEUED"
        queue.push_job(q_name, job)
        db.add_log(job_id, f"Scheduled job fired → pushed to {q_name}")
        logger.info(f"Fired scheduled job {job_id} → {q_name}")


# ── Recurring schedule firing ─────────────────────────────────────────────────

def _compute_next_run(schedule: dict, after: datetime) -> datetime:
    """Compute next run time from cron expression or interval."""
    cron = schedule.get("cron_expression")
    interval = schedule.get("interval_seconds")

    if cron:
        try:
            itr = croniter(cron, after)
            return itr.get_next(datetime).replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.error(f"Bad cron expression '{cron}': {e}")
            return None
    elif interval:
        from datetime import timedelta
        return after + timedelta(seconds=int(interval))
    return None


def _fire_recurring_schedules():
    due = db.get_due_schedules()
    for schedule in due:
        schedule_id = schedule["id"]
        now         = _utcnow()

        # Create a new job from the schedule template
        job_id = str(uuid.uuid4())
        job = {
            "id":          job_id,
            "type":        schedule["job_type"],
            "status":      "QUEUED",
            "priority":    schedule["priority"],
            "payload":     schedule.get("payload", {}),
            "created_at":  _utcnow_str(),
            "started_at":  None,
            "completed_at": None,
            "retry_count": 0,
            "worker_id":   None,
            "error":       None,
            "run_at":      None,
            "schedule_id": schedule_id,
        }
        db.save_job(job)

        q_name = PRIORITY_QUEUE_MAP.get(schedule["priority"], QUEUE_MEDIUM)
        queue.push_job(q_name, job)
        db.add_log(job_id, f"Created by recurring schedule '{schedule['name']}' → {q_name}")
        logger.info(f"Recurring schedule '{schedule['name']}' fired → job {job_id} → {q_name}")

        # Compute next run time
        next_run = _compute_next_run(schedule, now)
        if next_run:
            db.update_schedule(
                schedule_id,
                last_run_at=now,
                next_run_at=next_run,
                run_count=schedule.get("run_count", 0) + 1,
            )
            logger.info(f"Schedule '{schedule['name']}' next run: {next_run.isoformat()}")
        else:
            # Bad expression — deactivate to avoid infinite loop
            db.update_schedule(schedule_id, is_active=0)
            logger.error(f"Schedule '{schedule['name']}' deactivated — could not compute next_run")


# ── Main loop ─────────────────────────────────────────────────────────────────

def _scheduler_loop():
    global _running
    logger.info("Scheduler started")
    while _running:
        try:
            _fire_scheduled_jobs()
            _fire_recurring_schedules()
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        time.sleep(SCHEDULER_INTERVAL)
    logger.info("Scheduler stopped")


def start_scheduler():
    global _scheduler_thread, _running
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _running = True
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, daemon=True, name="scheduler"
    )
    _scheduler_thread.start()


def stop_scheduler():
    global _running
    _running = False
