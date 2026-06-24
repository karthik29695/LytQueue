"""
Phase 4: Observability metrics collected from MySQL.
- Execution time histograms per job type
- Jobs per minute throughput
- Slow job detection
- Per-worker performance breakdown
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from core import db

logger = logging.getLogger("metrics")

SLOW_JOB_THRESHOLD_SECONDS = 10  # jobs running longer than this are flagged


# ── Histogram buckets ─────────────────────────────────────────────────────────

HISTOGRAM_BUCKETS = [0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]

def _build_histogram(runtimes: list[float]) -> dict:
    """Build a histogram dict from a list of runtimes in seconds."""
    buckets = {}
    for b in HISTOGRAM_BUCKETS:
        label = f"<={b}s"
        buckets[label] = sum(1 for r in runtimes if r <= b)
    buckets[f">{HISTOGRAM_BUCKETS[-1]}s"] = sum(
        1 for r in runtimes if r > HISTOGRAM_BUCKETS[-1]
    )
    return buckets


# ── Runtime stats ─────────────────────────────────────────────────────────────

def get_runtime_stats_by_type() -> dict:
    """Return avg, min, max runtime and histogram per job type."""
    conn = db.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT type,
                       COUNT(*) as count,
                       AVG(TIMESTAMPDIFF(MICROSECOND, started_at, completed_at)) / 1000000 as avg_s,
                       MIN(TIMESTAMPDIFF(MICROSECOND, started_at, completed_at)) / 1000000 as min_s,
                       MAX(TIMESTAMPDIFF(MICROSECOND, started_at, completed_at)) / 1000000 as max_s
                FROM jobs
                WHERE status = 'COMPLETED'
                  AND started_at IS NOT NULL
                  AND completed_at IS NOT NULL
                GROUP BY type
            """)
            rows = cursor.fetchall()

            # Also fetch individual runtimes per type for histograms
            cursor.execute("""
                SELECT type,
                       TIMESTAMPDIFF(MICROSECOND, started_at, completed_at) / 1000000 as runtime_s
                FROM jobs
                WHERE status = 'COMPLETED'
                  AND started_at IS NOT NULL
                  AND completed_at IS NOT NULL
            """)
            runtime_rows = cursor.fetchall()
    finally:
        conn.close()

    # Group runtimes by type
    runtimes_by_type: dict[str, list[float]] = {}
    for row in runtime_rows:
        t = row["type"]
        runtimes_by_type.setdefault(t, []).append(float(row["runtime_s"]))

    result = {}
    for row in rows:
        t = row["type"]
        runtimes = runtimes_by_type.get(t, [])
        result[t] = {
            "count":     int(row["count"]),
            "avg_s":     round(float(row["avg_s"]), 3) if row["avg_s"] else None,
            "min_s":     round(float(row["min_s"]), 3) if row["min_s"] else None,
            "max_s":     round(float(row["max_s"]), 3) if row["max_s"] else None,
            "histogram": _build_histogram(runtimes),
        }
    return result


# ── Throughput ────────────────────────────────────────────────────────────────

def get_throughput(window_minutes: int = 60) -> dict:
    """
    Jobs completed per minute over the last window_minutes.
    Returns a list of {minute, count} buckets for charting.
    """
    conn = db.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    DATE_FORMAT(completed_at, '%%Y-%%m-%%d %%H:%%i:00') as minute,
                    COUNT(*) as count
                FROM jobs
                WHERE status = 'COMPLETED'
                  AND completed_at >= NOW() - INTERVAL %s MINUTE
                GROUP BY minute
                ORDER BY minute ASC
            """, (window_minutes,))
            rows = cursor.fetchall()
    finally:
        conn.close()

    total = sum(r["count"] for r in rows)
    elapsed_minutes = max(window_minutes, 1)
    avg_per_minute = round(total / elapsed_minutes, 2)

    return {
        "window_minutes":  window_minutes,
        "total_completed": total,
        "avg_per_minute":  avg_per_minute,
        "buckets":         [{"minute": r["minute"], "count": int(r["count"])} for r in rows],
    }


# ── Slow job detection ────────────────────────────────────────────────────────

def get_slow_jobs() -> list[dict]:
    """Return jobs currently RUNNING longer than SLOW_JOB_THRESHOLD_SECONDS."""
    conn = db.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, type, priority, worker_id, started_at,
                       TIMESTAMPDIFF(SECOND, started_at, NOW()) as running_for_s
                FROM jobs
                WHERE status = 'RUNNING'
                  AND started_at IS NOT NULL
                  AND TIMESTAMPDIFF(SECOND, started_at, NOW()) > %s
                ORDER BY running_for_s DESC
            """, (SLOW_JOB_THRESHOLD_SECONDS,))
            rows = cursor.fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get("started_at"), datetime):
            r["started_at"] = r["started_at"].isoformat()
        r["running_for_s"] = int(r["running_for_s"])
        result.append(r)
    return result


# ── Per-worker performance ────────────────────────────────────────────────────

def get_worker_performance() -> list[dict]:
    """Return per-worker stats: jobs done, avg runtime, success rate."""
    conn = db.get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    w.worker_id,
                    w.status,
                    w.jobs_processed,
                    w.last_heartbeat,
                    COUNT(j.id)                                                        as total_jobs,
                    SUM(j.status = 'COMPLETED')                                        as completed,
                    SUM(j.status = 'DEAD')                                             as dead,
                    AVG(CASE WHEN j.status = 'COMPLETED'
                             THEN TIMESTAMPDIFF(MICROSECOND, j.started_at, j.completed_at) / 1000000
                        END)                                                           as avg_runtime_s
                FROM workers w
                LEFT JOIN jobs j ON j.worker_id = w.worker_id
                                 AND j.started_at IS NOT NULL
                GROUP BY w.worker_id, w.status, w.jobs_processed, w.last_heartbeat
                ORDER BY w.worker_id
            """)
            rows = cursor.fetchall()
    finally:
        conn.close()

    result = []
    for row in rows:
        r = dict(row)
        if isinstance(r.get("last_heartbeat"), datetime):
            r["last_heartbeat"] = r["last_heartbeat"].isoformat()
        total = int(r["total_jobs"] or 0)
        completed = int(r["completed"] or 0)
        r["total_jobs"]     = total
        r["completed"]      = completed
        r["dead"]           = int(r["dead"] or 0)
        r["success_rate"]   = round(completed / total * 100, 1) if total > 0 else 0.0
        r["avg_runtime_s"]  = round(float(r["avg_runtime_s"]), 3) if r["avg_runtime_s"] else None
        result.append(r)
    return result


# ── Summary ───────────────────────────────────────────────────────────────────

def get_observability_summary() -> dict:
    """Single endpoint that returns all observability data."""
    return {
        "runtime_by_type":   get_runtime_stats_by_type(),
        "throughput":        get_throughput(window_minutes=60),
        "slow_jobs":         get_slow_jobs(),
        "worker_performance": get_worker_performance(),
    }
