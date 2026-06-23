from fastapi import APIRouter, HTTPException
from datetime import datetime

from api.models import Job, JobSubmitRequest, PRIORITY_QUEUE_MAP
from core import store, queue
from config import QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW, QUEUE_DLQ

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=201)
def submit_job(req: JobSubmitRequest):
    """Submit a new job to the queue."""
    job = Job(
        type=req.type,
        priority=req.priority,
        payload=req.payload,
    )
    job_dict = job.to_dict()

    # Persist metadata
    store.save_job(job_dict)

    # Push into correct priority queue
    queue_name = PRIORITY_QUEUE_MAP[req.priority]
    queue.push_job(queue_name, job_dict)

    return {"job_id": job.id, "status": job.status, "queue": queue_name}


@router.get("")
def list_jobs(status: str = None):
    """List all jobs, optionally filtered by status."""
    return store.list_jobs(status=status)


@router.get("/{job_id}")
def get_job(job_id: str):
    """Get a single job by ID."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/retry")
def retry_job(job_id: str):
    """Manually re-queue a FAILED or DEAD job."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("FAILED", "DEAD"):
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, only FAILED/DEAD jobs can be retried")

    updated = store.update_job(
        job_id,
        status="QUEUED",
        retry_count=0,
        error=None,
        started_at=None,
        completed_at=None,
    )
    queue_name = PRIORITY_QUEUE_MAP[job["priority"]]
    queue.push_job(queue_name, updated)
    return {"job_id": job_id, "status": "QUEUED", "message": "Job re-queued"}


@router.delete("/{job_id}")
def delete_job(job_id: str):
    """Delete a job record."""
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "RUNNING":
        raise HTTPException(status_code=400, detail="Cannot delete a RUNNING job")
    store.delete_job(job_id)
    return {"message": f"Job {job_id} deleted"}
