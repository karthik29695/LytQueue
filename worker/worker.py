"""
Worker node: polls Redis queues in priority order, executes jobs,
handles retries, and routes exhausted jobs to the Dead Letter Queue.
"""
import sys
import os
import time
import uuid
import signal
import logging
from datetime import datetime, timezone

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
from concurrent.futures import ThreadPoolExecutor

# Ensure project root is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW, QUEUE_DLQ,
    MAX_RETRIES, WORKER_POLL_INTERVAL,
)
from core import store, queue
from worker.job_handlers import execute_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("worker")

# Priority order: high is checked first
QUEUE_PRIORITY_ORDER = [QUEUE_HIGH, QUEUE_MEDIUM, QUEUE_LOW]


class Worker:
    def __init__(self, worker_id: str = None, threads: int = 2):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.threads = threads
        self.running = False
        self.executor = ThreadPoolExecutor(max_workers=threads)
        logger.info(f"Worker {self.worker_id} initialised ({threads} thread(s))")

    def start(self):
        self.running = True
        logger.info(f"Worker {self.worker_id} started — polling queues {QUEUE_PRIORITY_ORDER}")
        try:
            while self.running:
                result = queue.pop_job(QUEUE_PRIORITY_ORDER, timeout=2)
                if result is None:
                    continue  # nothing in queue, loop again
                q_name, job_data = result
                # Submit to thread pool so we can keep polling
                self.executor.submit(self._process_job, job_data, q_name)
        except KeyboardInterrupt:
            logger.info(f"Worker {self.worker_id} shutting down...")
        finally:
            self.executor.shutdown(wait=True)
            logger.info(f"Worker {self.worker_id} stopped.")

    def stop(self):
        self.running = False

    def _process_job(self, job_data: dict, queue_name: str):
        job_id = job_data["id"]
        job_type = job_data["type"]
        retry_count = job_data.get("retry_count", 0)

        logger.info(f"[{self.worker_id}] Picked up job {job_id} (type={job_type}, retry={retry_count}, queue={queue_name})")

        # Mark as RUNNING
        store.update_job(
            job_id,
            status="RUNNING",
            started_at=utcnow(),
            worker_id=self.worker_id,
        )

        try:
            result = execute_job(job_type, job_data.get("payload", {}))
            # SUCCESS
            store.update_job(
                job_id,
                status="COMPLETED",
                completed_at=utcnow(),
                error=None,
            )
            logger.info(f"[{self.worker_id}] ✓ Job {job_id} COMPLETED — {result}")

        except Exception as exc:
            error_msg = str(exc)
            new_retry_count = retry_count + 1
            logger.warning(f"[{self.worker_id}] ✗ Job {job_id} FAILED (attempt {new_retry_count}/{MAX_RETRIES}) — {error_msg}")

            if new_retry_count < MAX_RETRIES:
                # Re-queue for retry
                updated_job = store.update_job(
                    job_id,
                    status="QUEUED",
                    retry_count=new_retry_count,
                    error=error_msg,
                    started_at=None,
                )
                time.sleep(2 ** new_retry_count)  # exponential backoff
                queue.push_job(queue_name, updated_job)
                logger.info(f"[{self.worker_id}] ↻ Job {job_id} re-queued (retry {new_retry_count})")
            else:
                # Exhausted retries → Dead Letter Queue
                store.update_job(
                    job_id,
                    status="DEAD",
                    completed_at=utcnow(),
                    retry_count=new_retry_count,
                    error=error_msg,
                )
                job_data["retry_count"] = new_retry_count
                job_data["error"] = error_msg
                queue.push_job(QUEUE_DLQ, job_data)
                logger.error(f"[{self.worker_id}] ✗✗ Job {job_id} moved to DLQ after {MAX_RETRIES} attempts")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", default=None, help="Worker ID")
    parser.add_argument("--threads", type=int, default=2, help="Thread pool size")
    args = parser.parse_args()

    worker = Worker(worker_id=args.id, threads=args.threads)

    def _shutdown(sig, frame):
        worker.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    worker.start()
