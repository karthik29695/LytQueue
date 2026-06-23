from fastapi import APIRouter
from core import store, queue
from config import QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW, QUEUE_DLQ

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics():
    """Return system-wide job and queue metrics."""
    all_jobs = store.list_jobs()

    status_counts = {}
    for job in all_jobs:
        s = job["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    completed = [j for j in all_jobs if j["status"] == "COMPLETED" and j.get("started_at") and j.get("completed_at")]
    avg_runtime = None
    if completed:
        from datetime import datetime
        runtimes = []
        for j in completed:
            try:
                start = datetime.fromisoformat(j["started_at"])
                end = datetime.fromisoformat(j["completed_at"])
                runtimes.append((end - start).total_seconds())
            except Exception:
                pass
        if runtimes:
            avg_runtime = round(sum(runtimes) / len(runtimes), 2)

    total = len(all_jobs)
    completed_count = status_counts.get("COMPLETED", 0)
    success_rate = round(completed_count / total * 100, 1) if total > 0 else 0.0

    return {
        "jobs": {
            "total": total,
            "by_status": status_counts,
            "success_rate_pct": success_rate,
            "avg_runtime_seconds": avg_runtime,
        },
        "queues": {
            "high": queue.queue_length(QUEUE_HIGH),
            "medium": queue.queue_length(QUEUE_MEDIUM),
            "low": queue.queue_length(QUEUE_LOW),
            "dlq": queue.queue_length(QUEUE_DLQ),
        },
    }
