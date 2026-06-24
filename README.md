# Distributed Job Processing Platform

A scalable async job queue built with FastAPI, Redis, and Python workers.

## Stack
- **FastAPI** — REST API gateway
- **Redis** — Priority job queues (`high`, `medium`, `low`, `dlq`)
- **Python Worker** — ThreadPoolExecutor-based job executor with retries

---

## Quickstart

```bash
docker compose up --build
```

API available at: http://localhost:8000  
Swagger docs at: http://localhost:8000/docs

---

## API Reference

### Submit a job
```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"type": "email", "priority": "high", "payload": {"to": "user@example.com"}}'
```

### Check job status
```bash
curl http://localhost:8000/jobs/<job_id>
```

### List all jobs
```bash
curl http://localhost:8000/jobs
curl http://localhost:8000/jobs?status=COMPLETED
```

### Retry a failed job
```bash
curl -X POST http://localhost:8000/jobs/<job_id>/retry
```

### Delete a job
```bash
curl -X DELETE http://localhost:8000/jobs/<job_id>
```

### System metrics
```bash
curl http://localhost:8000/metrics
```

---

## Job Types

| Type | Description | Simulated Duration |
|------|-------------|-------------------|
| `email` | Sends an email | 0.5–1.5s |
| `report` | Generates a report | 1.0–3.0s |
| `image_processing` | Resizes/processes an image | 0.8–2.0s |
| `simulation` | Dummy load test workload | Configurable |

### Simulation payload options
```json
{
  "type": "simulation",
  "priority": "low",
  "payload": {
    "duration_seconds": 5,
    "fail_rate": 0.5
  }
}
```

---

## Fault Tolerance

- **Automatic retries**: up to 3 attempts with exponential backoff (2s, 4s)
- **Dead Letter Queue**: exhausted jobs moved to `queue:dlq`
- **Manual retry**: `POST /jobs/{id}/retry` re-queues FAILED or DEAD jobs

---

## Scaling Workers

To run multiple workers, scale the worker service:
```bash
docker compose up --scale worker=3
```

All workers compete for jobs from the same Redis queues.

---

## Roadmap

- [x] Phase 1 — FastAPI + Redis + single worker
- [x] Phase 2 — Multiple workers + MySQL persistence + Dashboard
- [x] Phase 3 — Priority queues + retry + DLQ *(partly done in Phase 1)*
- [ ] Phase 4 — Worker heartbeats + monitoring + metrics
