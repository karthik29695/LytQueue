from fastapi import APIRouter, HTTPException
from api.models import Job, JobSubmitRequest, PRIORITY_QUEUE_MAP
from core import queue
from core import db
from config import QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW, QUEUE_DLQ

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=201)
def submit_job(req: JobSubmitRequest):
    job = Job(type=req.type, priority=req.priority, payload=req.payload)
    job_dict = job.to_dict()
    db.save_job(job_dict)
    queue_name = PRIORITY_QUEUE_MAP[req.priority]
    queue.push_job(queue_name, job_dict)
    db.add_log(job.id, f"Job submitted to {queue_name}")
    return {"job_id": job.id, "status": job.status, "queue": queue_name}


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
    queue_name = PRIORITY_QUEUE_MAP[job["priority"]]
    queue.push_job(queue_name, updated)
    db.add_log(job_id, "Job manually re-queued via API")
    return {"job_id": job_id, "status": "QUEUED", "message": "Job re-queued"}


@router.delete("/{job_id}")
def delete_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] == "RUNNING":
        raise HTTPException(status_code=400, detail="Cannot delete a RUNNING job")
    db.delete_job(job_id)
    return {"message": f"Job {job_id} deleted"}
