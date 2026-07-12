"""Job queue management with SQLite."""

import logging
import sqlite3
from enum import StrEnum
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class JobState(StrEnum):
    """Job state enum."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job:
    """Job data structure."""

    def __init__(self, row: tuple):
        """Initialize job from database row."""
        self.id = row[0]
        self.file_path = row[1]
        self.slug = row[2]
        self.state = JobState(row[3])
        self.attempts = row[4]
        self.last_error = row[5]
        self.created_at = row[6]
        self.updated_at = row[7]
        self.next_retry_at = row[8]
        self.wp_post_id = row[9] if len(row) > 9 else None
        self.wp_url = row[10] if len(row) > 10 else None

    def __repr__(self):
        return f"<Job id={self.id} slug={self.slug} state={self.state} attempts={self.attempts}>"


def get_connection() -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    cursor = conn.cursor()

    # Create jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            slug TEXT,
            state TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            next_retry_at TIMESTAMP,
            wp_post_id INTEGER,
            wp_url TEXT
        )
    """)

    # Create indices for efficient queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_state_next_retry
        ON jobs(state, next_retry_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_slug
        ON jobs(slug)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_created_at
        ON jobs(created_at DESC)
    """)

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {settings.db_path}")


def enqueue_job(file_path: Path) -> int:
    """Enqueue a new job.

    Args:
        file_path: Path to the ZIP file

    Returns:
        Job ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO jobs (file_path, state) VALUES (?, ?)", (str(file_path), JobState.QUEUED.value)
    )

    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Enqueued job {job_id}: {file_path.name}")
    return job_id


def get_next_job() -> Job | None:
    """Get next job to process.

    Returns:
        Next job to process, or None if queue is empty
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get queued jobs or failed jobs ready for retry
    cursor.execute(
        """
        SELECT * FROM jobs
        WHERE wp_post_id IS NULL AND (state = ? OR (state = ? AND next_retry_at <= datetime('now')))
        ORDER BY created_at ASC
        LIMIT 1
    """,
        (JobState.QUEUED.value, JobState.FAILED.value),
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return Job(tuple(row))
    return None


def get_job_by_id(job_id: int) -> Job | None:
    """Get job by ID.

    Args:
        job_id: Job ID

    Returns:
        Job object or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return Job(tuple(row))
    return None


def update_job_state(
    job_id: int,
    state: JobState,
    slug: str | None = None,
    error: str | None = None,
    increment_attempts: bool = False,
    wp_post_id: int | None = None,
    wp_url: str | None = None,
):
    """Update job state.

    Args:
        job_id: Job ID
        state: New state
        slug: Post slug (optional)
        error: Error message (optional)
        increment_attempts: Whether to increment attempt counter
    """
    conn = get_connection()
    cursor = conn.cursor()

    updates = ["state = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [state.value]

    if slug:
        updates.append("slug = ?")
        params.append(slug)

    if error:
        updates.append("last_error = ?")
        params.append(error)

    if wp_post_id:
        updates.append("wp_post_id = ?")
        params.append(wp_post_id)

    if wp_url:
        updates.append("wp_url = ?")
        params.append(wp_url)

    if increment_attempts:
        updates.append("attempts = attempts + 1")

    # Calculate next retry time for failed jobs
    if state == JobState.FAILED and increment_attempts:
        cursor.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        current_attempts = row[0] if row else 0
        new_attempts = current_attempts + 1

        if new_attempts <= settings.max_retries:
            retry_delays = settings.get_retry_delays()
            delay_index = min(new_attempts - 1, len(retry_delays) - 1)
            delay_seconds = retry_delays[delay_index]

            updates.append("next_retry_at = datetime('now', ?)")
            params.append(f"+{delay_seconds} seconds")

            logger.info(
                f"Job {job_id} will retry in {delay_seconds}s (attempt {new_attempts}/{settings.max_retries})"
            )
        else:
            # Max retries reached, set next_retry_at to NULL
            updates.append("next_retry_at = NULL")
            logger.warning(f"Job {job_id} reached max retries ({settings.max_retries})")

    query = f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?"
    params.append(job_id)

    cursor.execute(query, params)
    conn.commit()
    conn.close()

    logger.debug(f"Updated job {job_id}: {state.value}")


def get_job_stats() -> dict:
    """Get job statistics.

    Returns:
        Dictionary with counts for each state
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT state, COUNT(*) FROM jobs GROUP BY state
    """)

    stats = {state.value: 0 for state in JobState}
    for row in cursor.fetchall():
        stats[row[0]] = row[1]

    conn.close()
    return stats


def get_recent_jobs(limit: int = 50) -> list[dict]:
    """Get recent jobs.

    Args:
        limit: Maximum number of jobs to return

    Returns:
        List of job dictionaries
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, file_path, slug, state, attempts, last_error, updated_at
        FROM jobs
        ORDER BY updated_at DESC
        LIMIT ?
    """,
        (limit,),
    )

    jobs = []
    for row in cursor.fetchall():
        jobs.append(
            {
                "id": row[0],
                "file": Path(row[1]).name if row[1] else None,
                "slug": row[2],
                "state": row[3],
                "attempts": row[4],
                "last_error": row[5],
                "updated_at": row[6],
            }
        )

    conn.close()
    return jobs


def cleanup_old_jobs(days: int = 30):
    """Delete jobs older than specified days.

    Args:
        days: Number of days to keep
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM jobs
        WHERE state IN (?, ?)
        AND updated_at < datetime('now', ?)
    """,
        (JobState.DONE.value, JobState.FAILED.value, f"-{days} days"),
    )

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old jobs")
    return deleted


def reset_stuck_jobs():
    """Reset jobs stuck in 'running' state.

    This is useful for recovery after crashes.
    Jobs stuck in 'running' for more than 1 hour are reset to 'queued'.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE jobs
        SET state = ?, updated_at = CURRENT_TIMESTAMP
        WHERE state = ?
        AND updated_at < datetime('now', '-1 hour')
    """,
        (JobState.QUEUED.value, JobState.RUNNING.value),
    )

    reset = cursor.rowcount
    conn.commit()
    conn.close()

    if reset > 0:
        logger.warning(f"Reset {reset} stuck jobs to queued")
    return reset
