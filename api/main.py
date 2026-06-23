from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes import jobs, metrics, dashboard
from core.db import init_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


app = FastAPI(
    title="Distributed Job Processing Platform",
    description="Async job queue with priority scheduling, retries, and dead-letter queues.",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router)
app.include_router(metrics.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}
