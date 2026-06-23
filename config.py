import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Queue names
QUEUE_HIGH = "queue:high"
QUEUE_MEDIUM = "queue:medium"
QUEUE_LOW = "queue:low"
QUEUE_DLQ = "queue:dlq"

# Worker config
MAX_RETRIES = 3
WORKER_POLL_INTERVAL = 1  # seconds
