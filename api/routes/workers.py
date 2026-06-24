from fastapi import APIRouter, HTTPException
from core import db
from datetime import datetime, timezone

router = APIRouter(prefix="/workers", tags=["workers"])


def _enrich_worker(w: dict) -> dict:
    last_hb = w.get("last_heartbeat")
    if last_hb:
        try:
            hb_time = datetime.fromisoformat(last_hb)
            if hb_time.tzinfo is None:
                hb_time = hb_time.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - hb_time).total_seconds()
            w["heartbeat_age_seconds"] = round(age, 1)
            w["heartbeat_healthy"] = age < 15
        except Exception:
            w["heartbeat_age_seconds"] = None
            w["heartbeat_healthy"] = False
    else:
        w["heartbeat_age_seconds"] = None
        w["heartbeat_healthy"] = False
    return w


@router.get("")
def list_workers():
    workers = db.list_workers()
    return [_enrich_worker(w) for w in workers]


@router.get("/{worker_id}")
def get_worker(worker_id: str):
    workers = db.list_workers()
    worker = next((w for w in workers if w["worker_id"] == worker_id), None)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    conn = db.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, type, status, priority, created_at, completed_at, retry_count
                FROM jobs WHERE worker_id = %s ORDER BY created_at DESC LIMIT 10
            """, (worker_id,))
            recent_jobs = cursor.fetchall()
            for j in recent_jobs:
                for f in ("created_at", "completed_at"):
                    if isinstance(j.get(f), datetime):
                        j[f] = j[f].isoformat()
    finally:
        conn.close()

    return {**_enrich_worker(worker), "recent_jobs": recent_jobs}
