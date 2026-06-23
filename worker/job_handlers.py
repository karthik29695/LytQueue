"""
Job type handlers.
Each handler simulates the work a real job would do.
In production these would call real services (SMTP, image libs, etc.)
"""
import time
import random
import logging

logger = logging.getLogger(__name__)


def handle_email(payload: dict) -> str:
    """Simulate sending an email."""
    to = payload.get("to", "user@example.com")
    subject = payload.get("subject", "No Subject")
    logger.info(f"  → Sending email to={to} subject='{subject}'")
    time.sleep(random.uniform(0.5, 1.5))  # simulate SMTP latency

    # Simulate occasional failure (10% chance)
    if random.random() < 0.10:
        raise RuntimeError("SMTP connection refused")

    return f"Email delivered to {to}"


def handle_report(payload: dict) -> str:
    """Simulate generating a report."""
    report_type = payload.get("report_type", "summary")
    logger.info(f"  → Generating {report_type} report")
    time.sleep(random.uniform(1.0, 3.0))  # reports take longer

    if random.random() < 0.05:
        raise RuntimeError("Report template not found")

    return f"Report '{report_type}' generated successfully"


def handle_image_processing(payload: dict) -> str:
    """Simulate image processing (resize, compress, etc.)."""
    image_url = payload.get("image_url", "https://example.com/img.jpg")
    operation = payload.get("operation", "resize")
    logger.info(f"  → Processing image op={operation} url={image_url}")
    time.sleep(random.uniform(0.8, 2.0))

    if random.random() < 0.08:
        raise RuntimeError("Image decode error: unsupported format")

    return f"Image {operation} complete"


def handle_simulation(payload: dict) -> str:
    """Dummy workload for load testing."""
    duration = float(payload.get("duration_seconds", random.uniform(0.5, 2.0)))
    fail_rate = float(payload.get("fail_rate", 0.0))
    logger.info(f"  → Simulation running for {duration:.1f}s (fail_rate={fail_rate})")
    time.sleep(duration)

    if random.random() < fail_rate:
        raise RuntimeError("Simulated failure")

    return f"Simulation completed in {duration:.1f}s"


# Registry: job type → handler function
JOB_HANDLERS = {
    "email": handle_email,
    "report": handle_report,
    "image_processing": handle_image_processing,
    "simulation": handle_simulation,
}


def execute_job(job_type: str, payload: dict) -> str:
    """Dispatch to the correct handler. Raises on failure."""
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        raise ValueError(f"Unknown job type: {job_type}")
    return handler(payload)
