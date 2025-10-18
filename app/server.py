"""FastAPI server for monitoring and control."""

import logging
import sqlite3
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app import __version__
from app.config import settings
from app.processor import process_zip, ProcessorError
from app.publisher import publish_post, PublisherError
from app.queue import (
    Job,
    JobState,
    get_job_stats,
    get_next_job,
    init_db,
    update_job_state,
)
from app.utils import notify_slack
from app.watcher import start_watcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Blog Pipeline", version=__version__)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "version": __version__}


@app.get("/status")
def status(limit: int = 50):
    """Get recent jobs status."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, file_path, slug, state, attempts, last_error, updated_at
        FROM jobs
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,))

    jobs = []
    for row in cursor.fetchall():
        jobs.append({
            "id": row[0],
            "file": Path(row[1]).name if row[1] else None,
            "slug": row[2],
            "state": row[3],
            "attempts": row[4],
            "last_error": row[5],
            "updated_at": row[6],
        })

    conn.close()

    return {
        "jobs": jobs,
        "stats": get_job_stats(),
    }


@app.post("/retry")
def retry(job_id: int):
    """Retry a failed job."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT state FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    if row[0] not in (JobState.FAILED.value, JobState.DONE.value):
        raise HTTPException(status_code=400, detail="Job is not failed or done")

    update_job_state(job_id, JobState.QUEUED)
    return {"ok": True, "message": f"Job {job_id} queued for retry"}


def process_jobs():
    """Background job processor."""
    logger.info("Starting job processor")

    while True:
        job = get_next_job()

        if not job:
            time.sleep(5)
            continue

        logger.info(f"Processing job {job.id}: {Path(job.file_path).name}")
        update_job_state(job.id, JobState.RUNNING)

        try:
            # Process ZIP
            post_data = process_zip(Path(job.file_path))
            update_job_state(job.id, JobState.RUNNING, slug=post_data.slug)

            # Publish to WordPress
            wp_post = publish_post(post_data)

            # Move to published
            published_path = settings.published_dir / Path(job.file_path).name
            Path(job.file_path).rename(published_path)

            # Success
            update_job_state(job.id, JobState.DONE)
            notify_slack(
                f"✅ [{post_data.slug}] Draft created: {wp_post['link']}",
                success=True
            )

        except (ProcessorError, PublisherError) as e:
            logger.error(f"Job {job.id} failed: {e}")
            update_job_state(
                job.id,
                JobState.FAILED,
                error=str(e),
                increment_attempts=True
            )

            if job.attempts + 1 >= settings.max_retries:
                notify_slack(
                    f"❌ [{job.slug or 'unknown'}] Failed permanently after {job.attempts + 1} attempts: {e}",
                    success=False
                )

        except Exception as e:
            logger.exception(f"Unexpected error in job {job.id}")
            update_job_state(
                job.id,
                JobState.FAILED,
                error=f"Unexpected error: {e}",
                increment_attempts=True
            )


def main():
    """Main entry point."""
    # Initialize
    init_db()
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    settings.published_dir.mkdir(parents=True, exist_ok=True)

    # Start background threads
    watcher_thread = threading.Thread(target=start_watcher, daemon=True)
    processor_thread = threading.Thread(target=process_jobs, daemon=True)

    watcher_thread.start()
    processor_thread.start()

    # Start API server
    import uvicorn
    uvicorn.run(
        app,
        host=settings.server_host,
        port=settings.server_port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
