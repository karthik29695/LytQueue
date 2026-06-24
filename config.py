import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Queue names
QUEUE_HIGH = "queue:high"
QUEUE_MEDIUM = "queue:medium"
QUEUE_LOW = "queue:low"
QUEUE_DLQ = "queue:dlq"

# MySQL config
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "jobuser")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "jobpass123")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "job_platform")

# Worker config
MAX_RETRIES = 3
WORKER_POLL_INTERVAL = 1  # seconds
