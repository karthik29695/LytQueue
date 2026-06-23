"""
Phase 1: In-memory job store.
Phase 2 will replace this with MySQL persistence.
"""
import threading
from datetime import datetime
from typing import Optional

_store: dict[str, dict] = {}
_lock = threading.Lock()


def save_job(job: dict) -> None:
    with _lock:
        _store[job["id"]] = job.copy()


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        return _store.get(job_id)


def update_job(job_id: str, **fields) -> Optional[dict]:
    with _lock:
        if job_id not in _store:
            return None
        _store[job_id].update(fields)
        return _store[job_id].copy()


def list_jobs(status: Optional[str] = None) -> list[dict]:
    with _lock:
        jobs = list(_store.values())
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)


def delete_job(job_id: str) -> bool:
    with _lock:
        if job_id not in _store:
            return False
        del _store[job_id]
        return True
