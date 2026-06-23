from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid


JobType = Literal["email", "report", "image_processing", "simulation"]
JobPriority = Literal["high", "medium", "low"]
JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "DEAD"]

PRIORITY_QUEUE_MAP = {
    "high": "queue:high",
    "medium": "queue:medium",
    "low": "queue:low",
}


class JobSubmitRequest(BaseModel):
    type: JobType
    priority: JobPriority = "medium"
    payload: dict = Field(default_factory=dict)


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType
    priority: JobPriority
    status: JobStatus = "QUEUED"
    payload: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    worker_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump()
