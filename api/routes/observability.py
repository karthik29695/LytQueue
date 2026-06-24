from fastapi import APIRouter
from core.metrics import (
    get_observability_summary,
    get_runtime_stats_by_type,
    get_throughput,
    get_slow_jobs,
    get_worker_performance,
)

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("")
def observability_summary():
    """All observability data in one call — used by the dashboard."""
    return get_observability_summary()


@router.get("/runtime")
def runtime_stats():
    """Execution time stats and histogram per job type."""
    return get_runtime_stats_by_type()


@router.get("/throughput")
def throughput(window_minutes: int = 60):
    """Jobs completed per minute over the last N minutes."""
    return get_throughput(window_minutes=window_minutes)


@router.get("/slow-jobs")
def slow_jobs():
    """Jobs currently running longer than the slow threshold."""
    return get_slow_jobs()


@router.get("/workers")
def worker_performance():
    """Per-worker performance breakdown."""
    return get_worker_performance()
