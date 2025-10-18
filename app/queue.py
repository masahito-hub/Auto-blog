"""Job queue management with SQLite."""

import logging
import sqlite3
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    """Job state enum."""
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Job:
    """Job data structure."""

    def __init__(self, row: tuple):
        self.id = row[0]
        self.file_path = row[1]
        self.slug = row[2]
        self.state = JobState(row[3])
        self.attempts = row[4]
        self.last_error = row[5]
        self.created_at = row[6]
        self.updated_at = row[7]
        self.next_retry_at = row[8]


def init_db():
    """Initialize database schema."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

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
            next_retry_at TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_state_next_retry
        ON jobs(state, next_retry_at)
    """)

    conn.commit()
    conn.close()
    logger.info("Database initialized")


def enqueue_job(file_path: Path) -> int:
    """Enqueue a new job."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO jobs (file_path, state) VALUES (?, ?)",
        (str(file_path), JobState.QUEUED.value)
    )

    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    logger.info(f"Enqueued job {job_id}: {file_path.name}")
    return job_id


def get_next_job() -> Optional[Job]:
    """Get next job to process."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    # Get queued jobs or failed jobs ready for retry
    cursor.execute("""
        SELECT * FROM jobs
        WHERE (state = ? OR (state = ? AND next_retry_at <= datetime('now')))
        ORDER BY created_at ASC
        LIMIT 1
    """, (JobState.QUEUED.value, JobState.FAILED.value))

    row = cursor.fetchone()
    conn.close()

    return Job(row) if row else None


def update_job_state(
    job_id: int,
    state: JobState,
    slug: Optional[str] = None,
    error: Optional[str] = None,
    increment_attempts: bool = False
):
    """Update job state."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    updates = ["state = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [state.value]

    if slug:
        updates.append("slug = ?")
        params.append(slug)

    if error:
        updates.append("last_error = ?")
        params.append(error)

    if increment_attempts:
        updates.append("attempts = attempts + 1")

    # Calculate next retry time for failed jobs
    if state == JobState.FAILED and increment_attempts:
        cursor.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,))
        attempts = cursor.fetchone()[0] + 1

        if attempts <= settings.max_retries:
            delay = settings.retry_delays[min(attempts - 1, len(settings.retry_delays) - 1)]
            updates.append("next_retry_at = datetime('now', ?)")  
            params.append(f"+{delay} seconds")

    query = f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?"
    params.append(job_id)

    cursor.execute(query, params)
    conn.commit()
    conn.close()

    logger.info(f"Updated job {job_id}: {state.value}")


def get_job_stats() -> dict:
    """Get job statistics."""
    conn = sqlite3.connect(settings.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT state, COUNT(*) FROM jobs GROUP BY state
    """)

    stats = {state.value: 0 for state in JobState}
    for row in cursor.fetchall():
        stats[row[0]] = row[1]

    conn.close()
    return stats
