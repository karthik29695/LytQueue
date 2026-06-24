"""
Worker node — Phase 3:
- Polls Redis queues in priority order
- Executes jobs with ThreadPoolExecutor
- Sends heartbeats to MySQL every 5s
- Graceful shutdown: finishes in-flight jobs before exiting
- Crash recovery handled by watchdog on API side
"""
import os
import sys
import time
import uuid
import signal
import logging
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW, QUEUE_DLQ,
    MAX_RETRIES,
)
from core import queue, db
from worker.job_handlers import execute_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("worker")

QUEUE_PRIORITY_ORDER = [QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW]
HEARTBEAT_INTERVAL  = 5   # seconds


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Worker:
    def __init__(self, worker_id: str = None, threads: int = 2):
        self.worker_id  = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.threads    = threads
        self.running    = False
        self._executor  = ThreadPoolExecutor(max_workers=threads)
        self._futures   = []          # track in-flight futures
        self._active_jobs: set[str] = set()
        self._lock      = threading.Lock()
        logger.info(f"Worker {self.worker_id} initialised ({threads} thread(s))")

    # ── lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        self.running = True
        db.init_schema()
        db.register_worker(self.worker_id)

        hb = threading.Thread(target=self._heartbeat_loop, daemon=True, name="heartbeat")
        hb.start()

        logger.info(f"Worker {self.worker_id} started — polling {QUEUE_PRIORITY_ORDER}")
        try:
            while self.running:
                result = queue.pop_job(QUEUE_PRIORITY_ORDER, timeout=2)
                if result is None:
                    continue
                q_name, job_data = result
                future = self._executor.submit(self._process_job, job_data, q_name)
                with self._lock:
                    self._futures.append(future)
                # Prune completed futures to avoid unbounded list
                with self._lock:
                    self._futures = [f for f in self._futures if not f.done()]

        except KeyboardInterrupt:
            pass
        finally:
            self._graceful_shutdown()

    def stop(self):
        """Signal the main loop to stop after finishing current jobs."""
        logger.info(f"Worker {self.worker_id} received stop signal — finishing in-flight jobs...")
        self.running = False

    def _graceful_shutdown(self):
        logger.info(f"Worker {self.worker_id} waiting for in-flight jobs to finish...")
        with self._lock:
            pending = list(self._futures)
        if pending:
            wait(pending, return_when=ALL_COMPLETED)
        self._executor.shutdown(wait=True)
        db.mark_worker_offline(self.worker_id)
        logger.info(f"Worker {self.worker_id} shut down cleanly.")

    # ── heartbeat ──────────────────────────────────────────────────────────

    def _heartbeat_loop(self):
        while self.running:
            try:
                with self._lock:
                    active = list(self._active_jobs)
                status      = "RUNNING" if active else "IDLE"
                current_job = active[0] if active else None
                db.heartbeat(self.worker_id, status, current_job)
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")
            time.sleep(HEARTBEAT_INTERVAL)

    # ── job execution ──────────────────────────────────────────────────────

    def _process_job(self, job_data: dict, queue_name: str):
        job_id      = job_data["id"]
        job_type    = job_data["type"]
        retry_count = job_data.get("retry_count", 0)

        with self._lock:
            self._active_jobs.add(job_id)

        logger.info(
            f"[{self.worker_id}] Picked up job {job_id} "
            f"(type={job_type}, retry={retry_count}, queue={queue_name})"
        )

        db.update_job(job_id, status="RUNNING", started_at=utcnow(), worker_id=self.worker_id)
        db.add_log(job_id, f"Picked up by {self.worker_id} from {queue_name}")

        try:
            result = execute_job(job_type, job_data.get("payload", {}))

            db.update_job(job_id, status="COMPLETED", completed_at=utcnow(), error=None)
            db.increment_jobs_processed(self.worker_id)
            db.add_log(job_id, f"COMPLETED: {result}")
            logger.info(f"[{self.worker_id}] ✓ Job {job_id} COMPLETED — {result}")

        except Exception as exc:
            error_msg  = str(exc)
            new_retry  = retry_count + 1
            logger.warning(
                f"[{self.worker_id}] ✗ Job {job_id} FAILED "
                f"(attempt {new_retry}/{MAX_RETRIES}) — {error_msg}"
            )
            db.add_log(job_id, f"FAILED attempt {new_retry}: {error_msg}")

            if new_retry < MAX_RETRIES:
                backoff = 2 ** new_retry
                updated = db.update_job(
                    job_id, status="QUEUED",
                    retry_count=new_retry, error=error_msg, started_at=None,
                )
                time.sleep(backoff)
                queue.push_job(queue_name, updated)
                db.add_log(job_id, f"Re-queued for retry {new_retry} (backoff {backoff}s)")
                logger.info(f"[{self.worker_id}] ↻ Job {job_id} re-queued (retry {new_retry})")
            else:
                db.update_job(
                    job_id, status="DEAD", completed_at=utcnow(),
                    retry_count=new_retry, error=error_msg,
                )
                job_data["retry_count"] = new_retry
                job_data["error"]       = error_msg
                queue.push_job(QUEUE_DLQ, job_data)
                db.add_log(job_id, f"Moved to DLQ after {MAX_RETRIES} failed attempts")
                logger.error(f"[{self.worker_id}] ✗✗ Job {job_id} → DLQ")

        finally:
            with self._lock:
                self._active_jobs.discard(job_id)


# ── entrypoint ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--id",      default=None)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()

    worker = Worker(worker_id=args.id, threads=args.threads)

    def _shutdown(sig, frame):
        worker.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)
    worker.start()
