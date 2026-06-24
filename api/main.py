import threading
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes import jobs, metrics, dashboard, workers, observability

logger = logging.getLogger("api")


def _startup_background():
    try:
        from core.db import init_schema
        init_schema()
        logger.info("Database schema initialised")
    except Exception as e:
        logger.error(f"DB init failed: {e}")
    try:
        from core.watchdog import start_watchdog
        start_watchdog()
        logger.info("Watchdog started")
    except Exception as e:
        logger.error(f"Watchdog start failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_startup_background, daemon=True, name="startup")
    t.start()
    yield
    try:
        from core.watchdog import stop_watchdog
        stop_watchdog()
    except Exception:
        pass


app = FastAPI(
    title="Distributed Job Processing Platform",
    description="Async job queue with priority scheduling, retries, dead-letter queues, crash recovery, and observability.",
    version="4.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(metrics.router)
app.include_router(workers.router)
app.include_router(observability.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "4.0.0"}
