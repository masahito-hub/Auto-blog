"""Tests for queue module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.queue import (
    Job,
    JobState,
    cleanup_old_jobs,
    enqueue_job,
    get_job_by_id,
    get_job_stats,
    get_next_job,
    get_recent_jobs,
    init_db,
    reset_stuck_jobs,
    update_job_state,
)


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """Create temporary database for testing."""
    db_path = tmp_path / "test_queue.db"
    
    # Mock settings
    from app import config
    monkeypatch.setattr(config.settings, "db_path", db_path)
    monkeypatch.setattr(config.settings, "max_retries", 3)
    monkeypatch.setattr(config.settings, "retry_delays", "60,300,900")
    
    # Initialize database
    init_db()
    
    yield db_path
    
    # Cleanup
    if db_path.exists():
        db_path.unlink()


def test_init_db(temp_db):
    """Test database initialization."""
    assert temp_db.exists()
    
    # Check table exists
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
    )
    assert cursor.fetchone() is not None
    conn.close()


def test_enqueue_job(temp_db):
    """Test enqueuing a job."""
    file_path = Path("/test/sample.zip")
    job_id = enqueue_job(file_path)
    
    assert job_id > 0
    
    # Verify in database
    job = get_job_by_id(job_id)
    assert job is not None
    assert job.file_path == str(file_path)
    assert job.state == JobState.QUEUED
    assert job.attempts == 0


def test_get_next_job(temp_db):
    """Test getting next job from queue."""
    # Empty queue
    assert get_next_job() is None
    
    # Add jobs
    job_id_1 = enqueue_job(Path("/test/file1.zip"))
    job_id_2 = enqueue_job(Path("/test/file2.zip"))
    
    # Get next job (should be first one)
    next_job = get_next_job()
    assert next_job is not None
    assert next_job.id == job_id_1
    
    # Mark as running
    update_job_state(job_id_1, JobState.RUNNING)
    
    # Get next job (should be second one)
    next_job = get_next_job()
    assert next_job.id == job_id_2


def test_update_job_state(temp_db):
    """Test updating job state."""
    job_id = enqueue_job(Path("/test/sample.zip"))
    
    # Update to running
    update_job_state(job_id, JobState.RUNNING, slug="test-post")
    
    job = get_job_by_id(job_id)
    assert job.state == JobState.RUNNING
    assert job.slug == "test-post"
    
    # Update to done
    update_job_state(job_id, JobState.DONE)
    
    job = get_job_by_id(job_id)
    assert job.state == JobState.DONE


def test_job_retry_logic(temp_db):
    """Test job retry with exponential backoff."""
    job_id = enqueue_job(Path("/test/sample.zip"))
    
    # Mark as running
    update_job_state(job_id, JobState.RUNNING)
    
    # Fail with retry
    update_job_state(
        job_id,
        JobState.FAILED,
        error="Test error",
        increment_attempts=True
    )
    
    job = get_job_by_id(job_id)
    assert job.state == JobState.FAILED
    assert job.attempts == 1
    assert job.last_error == "Test error"
    assert job.next_retry_at is not None


def test_get_job_stats(temp_db):
    """Test job statistics."""
    enqueue_job(Path("/test/file1.zip"))
    enqueue_job(Path("/test/file2.zip"))
    job_id_3 = enqueue_job(Path("/test/file3.zip"))
    
    update_job_state(job_id_3, JobState.RUNNING)
    
    stats = get_job_stats()
    assert stats[JobState.QUEUED.value] == 2
    assert stats[JobState.RUNNING.value] == 1
    assert stats[JobState.DONE.value] == 0
    assert stats[JobState.FAILED.value] == 0


def test_get_recent_jobs(temp_db):
    """Test getting recent jobs."""
    for i in range(5):
        enqueue_job(Path(f"/test/file{i}.zip"))
    
    jobs = get_recent_jobs(limit=3)
    assert len(jobs) == 3
    assert all(isinstance(job, dict) for job in jobs)
    assert all("id" in job for job in jobs)


def test_reset_stuck_jobs(temp_db):
    """Test resetting stuck jobs."""
    job_id = enqueue_job(Path("/test/sample.zip"))
    
    # Manually set to running with old timestamp
    from app import config
    conn = sqlite3.connect(config.settings.db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE jobs SET state = ?, updated_at = datetime('now', '-2 hours') WHERE id = ?",
        (JobState.RUNNING.value, job_id)
    )
    conn.commit()
    conn.close()
    
    # Reset stuck jobs
    reset_count = reset_stuck_jobs()
    assert reset_count == 1
    
    job = get_job_by_id(job_id)
    assert job.state == JobState.QUEUED
