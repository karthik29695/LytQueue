from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from croniter import croniter

from api.models import Schedule, ScheduleCreateRequest
from core import db
from core.scheduler import _compute_next_run

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _parse_first_run(req: ScheduleCreateRequest) -> datetime:
    """Compute the first next_run_at from cron or interval (always in the future)."""
    now = datetime.now(timezone.utc)
    fake_schedule = {
        "cron_expression":  req.cron_expression,
        "interval_seconds": req.interval_seconds,
    }
    next_run = _compute_next_run(fake_schedule, now)
    if not next_run:
        raise HTTPException(status_code=400, detail="Could not compute next run from schedule expression")
    return next_run


@router.post("", status_code=201)
def create_schedule(req: ScheduleCreateRequest):
    """Create a new recurring schedule."""
    # Validate cron expression if provided
    if req.cron_expression:
        try:
            croniter(req.cron_expression)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid cron expression: '{req.cron_expression}'")

    next_run = _parse_first_run(req)
    now_str  = datetime.now(timezone.utc).isoformat()

    schedule = Schedule(
        name=req.name,
        job_type=req.job_type,
        priority=req.priority,
        payload=req.payload,
        cron_expression=req.cron_expression,
        interval_seconds=req.interval_seconds,
        next_run_at=next_run.isoformat(),
        created_at=now_str,
    )
    db.save_schedule(schedule.to_dict())
    return schedule.to_dict()


@router.get("")
def list_schedules():
    """List all recurring schedules."""
    return db.list_schedules()


@router.get("/{schedule_id}")
def get_schedule(schedule_id: str):
    """Get a schedule with its recent jobs."""
    schedule = db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    recent_jobs = db.get_jobs_by_schedule(schedule_id)
    return {**schedule, "recent_jobs": recent_jobs}


@router.patch("/{schedule_id}/pause")
def pause_schedule(schedule_id: str):
    """Pause a recurring schedule."""
    schedule = db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if not schedule["is_active"]:
        raise HTTPException(status_code=400, detail="Schedule is already paused")
    db.update_schedule(schedule_id, is_active=0)
    return {"schedule_id": schedule_id, "status": "paused"}


@router.patch("/{schedule_id}/resume")
def resume_schedule(schedule_id: str):
    """Resume a paused schedule — recalculates next_run_at from now."""
    schedule = db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if schedule["is_active"]:
        raise HTTPException(status_code=400, detail="Schedule is already active")

    # Recalculate next_run from now so it doesn't fire all missed runs
    now = datetime.now(timezone.utc)
    next_run = _compute_next_run(schedule, now)
    if not next_run:
        raise HTTPException(status_code=400, detail="Could not compute next run time")

    db.update_schedule(schedule_id, is_active=1, next_run_at=next_run.isoformat())
    return {"schedule_id": schedule_id, "status": "resumed", "next_run_at": next_run.isoformat()}


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str):
    """Delete a recurring schedule (does not delete already-created jobs)."""
    schedule = db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete_schedule(schedule_id)
    return {"message": f"Schedule {schedule_id} deleted"}


@router.get("/{schedule_id}/jobs")
def schedule_jobs(schedule_id: str):
    """List jobs created by a recurring schedule."""
    schedule = db.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return db.get_jobs_by_schedule(schedule_id, limit=50)
