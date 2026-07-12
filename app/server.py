"""FastAPI server for monitoring and control."""

import logging
import signal
import sqlite3
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import __version__
from app.config import settings
from app.processor import ProcessorError, cleanup_work_dir, process_zip
from app.publisher import PublisherError, publish_post
from app.queue import (
    Job,
    JobState,
    get_job_stats,
    get_next_job,
    get_recent_jobs,
    init_db,
    reset_stuck_jobs,
    update_job_state,
)
from app.utils import notify_slack
from app.watcher import start_watcher

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Blog Pipeline", version=__version__)

# Global shutdown flag
shutdown_event = threading.Event()


class RetryRequest(BaseModel):
    """Request model for retry endpoint."""

    job_id: int


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "version": __version__}


@app.get("/status")
def status(limit: int = 50):
    """Get recent jobs status."""
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 1000")

    return {
        "jobs": get_recent_jobs(limit=limit),
        "stats": get_job_stats(),
    }


@app.post("/retry")
def retry(request: RetryRequest):
    """Retry a failed job."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT state FROM jobs WHERE id = ?", (request.job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    state = row[0]
    if state not in (JobState.FAILED.value, JobState.DONE.value):
        raise HTTPException(
            status_code=400,
            detail=f"Job is in '{state}' state. Can only retry 'failed' or 'done' jobs.",
        )

    # Reset to queued state
    update_job_state(request.job_id, JobState.QUEUED)
    logger.info(f"Manual retry requested for job {request.job_id}")

    return {"ok": True, "message": f"Job {request.job_id} queued for retry"}


def process_jobs():
    """Background job processor.

    This runs in a separate thread and continuously processes jobs from the queue.
    """
    logger.info("Starting job processor")

    while not shutdown_event.is_set():
        try:
            job = get_next_job()

            if not job:
                # No jobs available, sleep and check again
                time.sleep(5)
                continue

            process_single_job(job)

        except Exception as e:
            logger.exception(f"Unexpected error in job processor: {e}")
            time.sleep(10)  # Back off on unexpected errors

    logger.info("Job processor stopped")


def process_single_job(job: Job):
    """Process a single job.

    Args:
        job: Job to process
    """
    file_path = Path(job.file_path)
    logger.info(f"Processing job {job.id}: {file_path.name}")

    # Update to running state
    update_job_state(job.id, JobState.RUNNING)

    try:
        # Step 1: Process ZIP (extract, parse, convert)
        post_data = process_zip(file_path)

        # Update job with slug
        update_job_state(job.id, JobState.RUNNING, slug=post_data.slug)
        logger.info(f"Job {job.id}: Parsed post '{post_data.slug}'")

        # Step 2: Publish to WordPress
        wp_post = publish_post(post_data)
        logger.info(f"Job {job.id}: Published to WordPress: {wp_post['link']}")

        # Step 3: Move ZIP to published directory
        published_path = settings.published_dir / file_path.name

        # Handle filename collision
        if published_path.exists():
            base = published_path.stem
            ext = published_path.suffix
            counter = 1
            while published_path.exists():
                published_path = settings.published_dir / f"{base}-{counter}{ext}"
                counter += 1

        file_path.rename(published_path)
        logger.info(f"Job {job.id}: Moved to published: {published_path.name}")

        # Step 4: Clean up work directory
        cleanup_work_dir(post_data.work_dir)

        # Step 5: Mark as done
        update_job_state(job.id, JobState.DONE)

        # Step 6: Send success notification
        notify_slack(f"✅ [{post_data.slug}] Draft created: {wp_post['link']}", success=True)

        logger.info(f"Job {job.id}: Completed successfully")

    except (ProcessorError, PublisherError) as e:
        # Expected errors - log and retry
        error_msg = str(e)
        logger.error(f"Job {job.id} failed: {error_msg}")

        # Update job state to failed (will auto-retry if not at max attempts)
        update_job_state(job.id, JobState.FAILED, error=error_msg, increment_attempts=True)

        # Check if this is the final failure
        attempts = job.attempts + 1
        if attempts >= settings.max_retries:
            notify_slack(
                f"❌ [{job.slug or file_path.stem}] Failed permanently after {attempts} attempts:\n{error_msg}",
                success=False,
            )
        else:
            logger.info(f"Job {job.id}: Will retry (attempt {attempts}/{settings.max_retries})")

    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error: {e}"
        logger.exception(f"Job {job.id}: {error_msg}")

        update_job_state(job.id, JobState.FAILED, error=error_msg, increment_attempts=True)

        attempts = job.attempts + 1
        if attempts >= settings.max_retries:
            notify_slack(
                f"❌ [{job.slug or file_path.stem}] Failed permanently with unexpected error:\n{error_msg}",
                success=False,
            )


def signal_handler(signum, frame):
    """Handle shutdown signals.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


def main():
    """Main entry point."""
    logger.info(f"Starting Blog Pipeline v{__version__}")

    # Validate configuration
    errors = settings.validate_environment()
    if errors:
        logger.error("Configuration validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\nPlease fix configuration errors and try again.")
        logger.error("Run 'python scripts/check_config.py' for detailed checks.")
        sys.exit(1)

    logger.info("Configuration validated successfully")

    # Initialize database
    init_db()

    # Reset any stuck jobs from previous run
    reset_count = reset_stuck_jobs()
    if reset_count > 0:
        logger.warning(f"Reset {reset_count} stuck jobs from previous run")

    # Ensure directories exist
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    settings.published_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Directories initialized")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start background threads
    logger.info("Starting background threads...")

    watcher_thread = threading.Thread(target=start_watcher, name="Watcher", daemon=True)

    processor_thread = threading.Thread(target=process_jobs, name="Processor", daemon=True)

    watcher_thread.start()
    processor_thread.start()

    logger.info("Background threads started")
    logger.info(f"Monitoring inbox: {settings.inbox_dir}")
    logger.info(f"API server starting on {settings.server_host}:{settings.server_port}")

    # Start API server (blocking)
    import uvicorn

    try:
        uvicorn.run(
            app,
            host=settings.server_host,
            port=settings.server_port,
            log_level=settings.log_level.lower(),
            access_log=False,  # Reduce noise
        )
    except Exception as e:
        logger.exception(f"Server error: {e}")
    finally:
        logger.info("Shutting down...")
        shutdown_event.set()

        # Wait for threads to finish (with timeout)
        watcher_thread.join(timeout=5)
        processor_thread.join(timeout=5)

        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
