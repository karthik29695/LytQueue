from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from api.models import Job, JobSubmitRequest, PRIORITY_QUEUE_MAP
from core import queue, db

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=201)
def submit_job(req: JobSubmitRequest):
    """Submit an immediate or one-time scheduled job."""
    now = datetime.now(timezone.utc)

    # Determine if this is a future scheduled job
    is_scheduled = req.run_at and req.run_at > now
    status  = "SCHEDULED" if is_scheduled else "QUEUED"
    run_at  = req.run_at.isoformat() if req.run_at else None

    job = Job(
        type=req.type, priority=req.priority,
        payload=req.payload, status=status, run_at=run_at,
    )
    job_dict = job.to_dict()
    db.save_job(job_dict)

    if not is_scheduled:
        q_name = PRIORITY_QUEUE_MAP[req.priority]
        queue.push_job(q_name, job_dict)
        db.add_log(job.id, f"Job submitted → {q_name}")
        return {"job_id": job.id, "status": status, "queue": q_name}
    else:
        db.add_log(job.id, f"Job scheduled for {run_at}")
        return {"job_id": job.id, "status": status, "run_at": run_at}


@router.get("/scheduled")
def list_scheduled():
    """List all pending one-time scheduled jobs."""
    return db.list_scheduled_jobs()


@router.get("")
def list_jobs(status: str = None):
    return db.list_jobs(status=status)


@router.get("/{job_id}")
def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/logs")
def get_job_logs(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return db.get_logs(job_id)


@router.post("/{job_id}/retry")
def retry_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("FAILED", "DEAD"):
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, only FAILED/DEAD jobs can be retried")
    updated = db.update_job(job_id, status="QUEUED", retry_count=0,
                            error=None, started_at=None, completed_at=None)
    q_name = PRIORITY_QUEUE_MAP[job["priority"]]
    queue.push_job(q_name, updated)
    db.add_log(job_id, "Job manually re-queued via API")
    return {"job_id": job_id, "status": "QUEUED", "message": "Job re-queued"}


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    """Cancel a SCHEDULED job before it runs."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "SCHEDULED":
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, only SCHEDULED jobs can be cancelled")
    db.update_job(job_id, status="DEAD", error="Cancelled by user")
    db.add_log(job_id, "Job cancelled by user")
    return {"job_id": job_id, "status": "DEAD", "message": "Scheduled job cancelled"}


@router.delete("/{job_id}")
def delete_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "RUNNING":
        raise HTTPException(status_code=400, detail="Cannot delete a RUNNING job")
    db.delete_job(job_id)
    return {"message": f"Job {job_id} deleted"}
