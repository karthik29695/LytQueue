from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

JobType     = Literal["email", "report", "image_processing", "simulation"]
JobPriority = Literal["high", "medium", "low"]
JobStatus   = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "DEAD", "SCHEDULED"]

PRIORITY_QUEUE_MAP = {
    "high":   "queue:high",
    "medium": "queue:medium",
    "low":    "queue:low",
}


def utcnow_str() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobSubmitRequest(BaseModel):
    type:     JobType
    priority: JobPriority = "medium"
    payload:  dict        = Field(default_factory=dict)
    run_at:   Optional[datetime] = None   # None = immediate


class ScheduleCreateRequest(BaseModel):
    name:              str
    job_type:          JobType
    priority:          JobPriority       = "medium"
    payload:           dict              = Field(default_factory=dict)
    cron_expression:   Optional[str]     = None   # e.g. "0 * * * *"
    interval_seconds:  Optional[int]     = None   # e.g. 3600

    @model_validator(mode="after")
    def must_have_one_schedule_type(self):
        if not self.cron_expression and not self.interval_seconds:
            raise ValueError("Provide either cron_expression or interval_seconds")
        if self.cron_expression and self.interval_seconds:
            raise ValueError("Provide only one of cron_expression or interval_seconds")
        return self


class Job(BaseModel):
    id:           str          = Field(default_factory=lambda: str(uuid.uuid4()))
    type:         JobType
    priority:     JobPriority
    status:       JobStatus    = "QUEUED"
    payload:      dict         = Field(default_factory=dict)
    created_at:   str          = Field(default_factory=utcnow_str)
    started_at:   Optional[str] = None
    completed_at: Optional[str] = None
    retry_count:  int          = 0
    worker_id:    Optional[str] = None
    error:        Optional[str] = None
    run_at:       Optional[str] = None
    schedule_id:  Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump()


class Schedule(BaseModel):
    id:               str          = Field(default_factory=lambda: str(uuid.uuid4()))
    name:             str
    job_type:         JobType
    priority:         JobPriority  = "medium"
    payload:          dict         = Field(default_factory=dict)
    cron_expression:  Optional[str] = None
    interval_seconds: Optional[int] = None
    next_run_at:      str
    last_run_at:      Optional[str] = None
    is_active:        bool         = True
    created_at:       str          = Field(default_factory=utcnow_str)
    run_count:        int          = 0

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["is_active"] = 1 if d["is_active"] else 0
        return d
