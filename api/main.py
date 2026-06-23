from fastapi import FastAPI
from api.routes import jobs, metrics

app = FastAPI(
    title="Distributed Job Processing Platform",
    description="Async job queue with priority scheduling, retries, and dead-letter queues.",
    version="1.0.0",
)

app.include_router(jobs.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
