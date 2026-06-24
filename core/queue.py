import redis
import json
from config import REDIS_HOST, REDIS_PORT, REDIS_DB

# Singleton Redis client
_client = None

def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=5,
    )
    return _client


def push_job(queue_name: str, job_data: dict) -> None:
    """Push a job dict onto the left side of a Redis list (queue)."""
    client = get_redis()
    client.lpush(queue_name, json.dumps(job_data))


def pop_job(queue_names: list[str], timeout: int = 2) -> tuple[str, dict] | None:
    """
    Blocking pop from multiple queues in priority order.
    Returns (queue_name, job_dict) or None on timeout.
    """
    client = get_redis()
    result = client.brpop(queue_names, timeout=timeout)
    if result is None:
        return None
    queue_name, raw = result
    return queue_name, json.loads(raw)


def queue_length(queue_name: str) -> int:
    """Return the current length of a queue."""
    return get_redis().llen(queue_name)


def requeue_job(queue_name: str, job_data: dict) -> None:
    """Re-push a job to the right side so it's processed next."""
    client = get_redis()
    client.rpush(queue_name, json.dumps(job_data))
