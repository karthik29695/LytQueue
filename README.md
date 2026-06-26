<div align="center">

# ⚡ LytQueue

### Distributed Job Processing Platform

A fault-tolerant distributed task processing system built with FastAPI, Redis, MySQL, and Python worker nodes.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green.svg)]()
[![Redis](https://img.shields.io/badge/Redis-Queue-red.svg)]()
[![MySQL](https://img.shields.io/badge/MySQL-Persistence-orange.svg)]()
[![Docker](https://img.shields.io/badge/Docker-Containerized-blue.svg)]()

**Priority Scheduling • Fault Tolerance • Crash Recovery • Observability • Horizontal Scaling**

</div>

---

## 🚀 Overview

LytQueue is a distributed job processing platform designed to execute asynchronous workloads across multiple worker nodes.

Inspired by systems such as Celery, AWS SQS, and Google Cloud Tasks, it provides:

- ⚡ Asynchronous Task Execution
- 📊 Real-Time Monitoring Dashboard
- 🔄 Automatic Retries with Exponential Backoff
- 💀 Dead Letter Queue (DLQ)
- ❤️ Heartbeat-Based Worker Monitoring
- 🛡️ Crash Recovery & Job Reassignment
- 📈 Throughput & Runtime Analytics
- 📦 Horizontal Worker Scaling

---

## 🏗️ Architecture

```text
                    Client
                       │
                       ▼
                FastAPI Gateway
                       │
                       ▼
                 Redis Queues
       ┌──────────┬──────────┬──────────┐
       ▼          ▼          ▼
  queue:high  queue:medium  queue:low
       │          │          │
       └──────────┴──────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  Worker Pool    │
         └─────────────────┘
                  │
                  ▼
                MySQL
                  │
                  ▼
          Monitoring Dashboard
```

---

## ✨ Features

| Category | Features |
|-----------|-----------|
| Queueing | High / Medium / Low Priority Queues |
| Reliability | Automatic Retries, DLQ |
| Recovery | Watchdog-Based Job Recovery |
| Monitoring | Worker Health, Queue Depths |
| Observability | Throughput, Runtime Analytics |
| Scalability | Multiple Worker Nodes |
| Persistence | MySQL Job Storage |
| Deployment | Docker Compose |

---

## 🔄 Job Lifecycle

### Successful Job

```text
QUEUED
   ↓
RUNNING
   ↓
COMPLETED
```

### Failed Job

```text
QUEUED
   ↓
RUNNING
   ↓
FAILED
   ↓
RETRY #1
   ↓
RETRY #2
   ↓
RETRY #3
   ↓
DEAD LETTER QUEUE
```

---

## ❤️ Worker Recovery

When a worker crashes during execution:

```text
Worker Processing Job
          │
          ▼
      Worker Crash
          │
          ▼
 Heartbeat Timeout
          │
          ▼
 Watchdog Detection
          │
          ▼
 Job Requeued
          │
          ▼
 Healthy Worker Picks Job
```

This ensures jobs are not permanently lost during worker failures.

---

## 📊 Dashboard

The monitoring dashboard provides:

### Job Metrics

- Total Jobs
- Running Jobs
- Queued Jobs
- Completed Jobs
- Failed Jobs
- Success Rate
- Average Runtime

### Queue Metrics

- High Queue Depth
- Medium Queue Depth
- Low Queue Depth
- DLQ Depth

### Worker Metrics

- Worker Health
- Last Heartbeat
- Success Rate
- Jobs Processed
- Runtime Statistics

### Analytics

- Throughput Tracking
- Runtime Distribution
- Job Type Performance
- Worker Utilization

---

## ⚙️ Tech Stack

### Backend

```yaml
FastAPI
Python
ThreadPoolExecutor
```

### Queue Engine

```yaml
Redis
Memurai
```

### Persistence

```yaml
MySQL
```

### Deployment

```yaml
Docker
Docker Compose
```

---

## 🚀 Quick Start

### Clone Repository

```bash
git clone https://github.com/karthik29695/LytQueue.git
cd LytQueue
```

### Start Services

```bash
docker compose up --build
```

### Access

```text
API        → http://localhost:8000
Swagger    → http://localhost:8000/docs
Dashboard  → http://localhost:8000/dashboard
```

---

## 📡 API Examples

### Submit Job

```bash
curl -X POST http://localhost:8000/jobs \
-H "Content-Type: application/json" \
-d '{
  "type": "email",
  "priority": "high",
  "payload": {
    "to": "user@example.com"
  }
}'
```

### Get Job Status

```bash
curl http://localhost:8000/jobs/{job_id}
```

### Retry Failed Job

```bash
curl -X POST http://localhost:8000/jobs/{job_id}/retry
```

---

## 📈 Benchmark Goals

| Jobs | Workers |
|--------|---------|
| 100 | 1 |
| 500 | 3 |
| 1000 | 3 |
| 5000 | 5 |

Metrics tracked:

- Throughput
- Success Rate
- Retry Count
- Queue Wait Time
- Average Runtime

---

## 🔮 Roadmap

- [x] Multi-Worker Processing
- [x] Priority Queues
- [x] Dead Letter Queue
- [x] Worker Heartbeats
- [x] Crash Recovery
- [x] Monitoring Dashboard
- [x] Scheduled Jobs
- [x] Recurring Jobs
- [ ] JWT Authentication
- [ ] Auto Scaling
- [ ] Prometheus Integration

---

## 🧠 Distributed Systems Concepts

- Concurrent Execution
- Worker Coordination
- Priority Scheduling
- Fault Tolerance
- Crash Recovery
- Retry Mechanisms
- Observability
- Horizontal Scaling
- Distributed Processing

---

<div align="center">

Built with ❤️ by **Karthik Gumballi**

</div>