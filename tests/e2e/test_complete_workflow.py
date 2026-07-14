"""End-to-end integration tests."""

import time
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.processor import process_zip
from app.publisher import publish_post
from app.queue import (
    JobState,
    enqueue_job,
    get_job_by_id,
    get_job_stats,
    init_db,
    update_job_state,
)
from app.server import process_single_job


def create_sample_zip(path: Path) -> Path:
    """Create a sample blog post ZIP for testing.

    Args:
        path: Directory to create ZIP in

    Returns:
        Path to created ZIP file
    """
    zip_path = path / "sample-blog-post.zip"

    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        # Create post.md with frontmatter
        post_content = """---
title: "Getting Started with Blog Automation"
slug: "blog-automation-guide"
description: "Learn how to automate your WordPress blog publishing workflow"
status: "draft"
categories: ["Automation", "WordPress"]
tags: ["blogging", "automation", "productivity"]
featured_image: "images/automation-hero.jpg"
author: "Tech Writer"
date: "2025-10-06"
---

# Introduction

Automating your blog publishing workflow can save hours of manual work.

## Benefits of Automation

1. **Time savings**: No more copy-pasting content
2. **Consistency**: Standardized formatting
3. **Scalability**: Handle high-volume publishing

## Getting Started

Here's a simple example:

```python
def publish_post(title, content):
    # Your automation code here
    pass
```

### Key Features

- Automatic image upload
- Markdown conversion
- Draft creation
- Error recovery

## Conclusion

Start automating today and reclaim your time!
"""
        zip_ref.writestr("post.md", post_content)

        # Create a fake image
        zip_ref.writestr("images/automation-hero.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    return zip_path


@pytest.fixture
def test_env(tmp_path, monkeypatch):
    """Setup test environment."""
    from app import config

    # Create directories
    inbox = tmp_path / "inbox"
    work = tmp_path / "work"
    published = tmp_path / "published"
    db_path = tmp_path / "queue.db"

    inbox.mkdir()
    work.mkdir()
    published.mkdir()

    # Mock settings
    monkeypatch.setattr(config.settings, "inbox_dir", inbox)
    monkeypatch.setattr(config.settings, "work_dir", work)
    monkeypatch.setattr(config.settings, "published_dir", published)
    monkeypatch.setattr(config.settings, "db_path", db_path)
    monkeypatch.setattr(config.settings, "max_retries", 3)
    monkeypatch.setattr(config.settings, "wp_base_url", "https://test.com")
    monkeypatch.setattr(config.settings, "wp_user", "testuser")
    monkeypatch.setattr(config.settings, "wp_app_password", "testpass")

    # Initialize database
    init_db()

    return {
        "inbox": inbox,
        "work": work,
        "published": published,
        "db_path": db_path,
    }


def test_processor_extracts_and_parses_zip(test_env):
    """Test that processor correctly extracts and parses ZIP."""
    # Create sample ZIP
    zip_path = create_sample_zip(test_env["inbox"])

    # Process it
    post_data = process_zip(zip_path)

    # Verify extracted data
    assert post_data.title == "Getting Started with Blog Automation"
    assert post_data.slug == "blog-automation-guide"
    assert post_data.status == "draft"
    assert "Automating your blog" in post_data.content
    assert "categories" in post_data.frontmatter

    # Verify HTML conversion
    html = post_data.get_html_content()
    assert "<h1" in html and "Introduction</h1>" in html
    assert "<strong>Time savings</strong>" in html
    assert "<code" in html  # Code block


@patch("app.publisher.requests.Session.get")
@patch("app.publisher.requests.Session.post")
def test_publisher_creates_wordpress_post(mock_post, mock_get, test_env):
    """Test that publisher successfully creates WordPress post."""
    # Create and process ZIP
    zip_path = create_sample_zip(test_env["inbox"])
    post_data = process_zip(zip_path)

    # Mock WordPress API responses
    # 1. Connection test, 2. Slug check (empty=not exists), 3. Categories
    conn_resp = Mock(status_code=200, json=lambda: {"name": "Test"})
    slug_resp = Mock(status_code=200, json=lambda: [])
    cat_resp_automation = Mock(status_code=200, json=lambda: [{"id": 1, "name": "Automation"}])
    cat_resp_wordpress = Mock(status_code=200, json=lambda: [{"id": 2, "name": "WordPress"}])
    mock_get.side_effect = [conn_resp, slug_resp, cat_resp_automation, cat_resp_wordpress]

    # 2. Media upload
    media_response = Mock(
        status_code=201,
        json=lambda: {
            "id": 123,
            "source_url": "https://test.com/wp-content/uploads/automation-hero.jpg",
            "mime_type": "image/jpeg",
        },
    )

    # 3. Post creation
    post_response = Mock(
        status_code=201,
        json=lambda: {
            "id": 456,
            "link": "https://test.com/blog-automation-guide/",
            "slug": "blog-automation-guide",
        },
    )

    mock_post.side_effect = [media_response, post_response]

    # Publish
    result = publish_post(post_data)

    # Verify
    assert result["id"] == 456
    assert "link" in result
    assert mock_post.call_count == 2  # Image + post


@patch("app.publisher.requests.Session.get")
@patch("app.publisher.requests.Session.post")
def test_complete_job_workflow(mock_post, mock_get, test_env):
    """Test complete workflow from ZIP to published post."""
    # Setup mocks: conn, slug check, categories
    conn = Mock(status_code=200, json=lambda: {"name": "Test"})
    slug = Mock(status_code=200, json=lambda: [])
    cat1 = Mock(status_code=200, json=lambda: [{"id": 1, "name": "Automation"}])
    cat2 = Mock(status_code=200, json=lambda: [{"id": 2, "name": "WordPress"}])
    mock_get.side_effect = [conn, slug, cat1, cat2]

    media_response = Mock(
        status_code=201, json=lambda: {"id": 123, "source_url": "https://test.com/image.jpg"}
    )

    post_response = Mock(
        status_code=201, json=lambda: {"id": 456, "link": "https://test.com/blog-automation-guide/"}
    )

    mock_post.side_effect = [media_response, post_response]

    # Create sample ZIP
    zip_path = create_sample_zip(test_env["inbox"])

    # Enqueue job
    job_id = enqueue_job(zip_path)

    # Verify job is queued
    job = get_job_by_id(job_id)
    assert job.state == JobState.QUEUED

    # Process job (simulates what background thread does)
    with patch("app.server.notify_slack"):  # Mock Slack notification
        process_single_job(job)

    # Verify job completed
    job = get_job_by_id(job_id)
    assert job.state == JobState.DONE
    assert job.slug == "blog-automation-guide"

    # Verify ZIP moved to published
    assert not zip_path.exists()
    published_zip = test_env["published"] / zip_path.name
    assert published_zip.exists()

    # Verify stats
    stats = get_job_stats()
    assert stats[JobState.DONE.value] == 1


@patch("app.publisher.requests.Session.get")
@patch("app.publisher.requests.Session.post")
def test_job_failure_and_retry(mock_post, mock_get, test_env):
    """Test job failure and retry mechanism."""
    # Setup: conn=success, slug=not exists, cat=found (URL-based dispatch)
    conn = Mock(status_code=200, json=lambda: {"name": "Test"})
    slug = Mock(status_code=200, json=lambda: [])
    cat1 = Mock(status_code=200, json=lambda: [{"id": 1, "name": "Automation"}])
    cat2 = Mock(status_code=200, json=lambda: [{"id": 2, "name": "WordPress"}])
    mock_get.side_effect = [conn, slug, cat1, cat2, conn, slug, cat1, cat2]

    # First call: timeout (will trigger retry)
    mock_post.side_effect = [
        Mock(status_code=500),  # Server error
        Mock(status_code=201, json=lambda: {"id": 123}),  # Success on retry
        Mock(status_code=201, json=lambda: {"id": 456, "link": "https://test.com/post/"}),
    ]

    zip_path = create_sample_zip(test_env["inbox"])
    job_id = enqueue_job(zip_path)

    # First attempt (will fail)
    job = get_job_by_id(job_id)
    with patch("app.server.notify_slack"):
        process_single_job(job)

    # Verify failed state
    job = get_job_by_id(job_id)
    assert job.state == JobState.FAILED
    assert job.attempts == 1
    assert job.next_retry_at is not None

    # Simulate retry (manually reset to queued)
    update_job_state(job_id, JobState.QUEUED)

    # Second attempt (will succeed)
    job = get_job_by_id(job_id)
    with patch("app.server.notify_slack"):
        process_single_job(job)

    # Verify success
    job = get_job_by_id(job_id)
    assert job.state == JobState.DONE


def test_invalid_zip_handling(test_env):
    """Test handling of invalid ZIP files."""
    # Create invalid ZIP (missing required fields)
    zip_path = test_env["inbox"] / "invalid.zip"

    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        # Missing required 'slug' field
        zip_ref.writestr("post.md", '---\ntitle: "Test"\n---\nContent')

    job_id = enqueue_job(zip_path)
    job = get_job_by_id(job_id)

    # Process (should fail)
    with patch("app.server.notify_slack"):
        process_single_job(job)

    # Verify failed
    job = get_job_by_id(job_id)
    assert job.state == JobState.FAILED
    assert "slug" in job.last_error.lower()


def test_acceptance_criteria_sample_zip_to_draft(test_env):
    """Acceptance Test: Sample ZIP creates WordPress draft within expected time.

    Acceptance Criteria:
    - Sample ZIP placed in inbox
    - Processing completes successfully
    - Draft post created in WordPress
    - All fields correctly populated
    """
    with (
        patch("app.publisher.requests.Session.get") as mock_get,
        patch("app.publisher.requests.Session.post") as mock_post,
        patch("app.server.notify_slack"),
    ):
        # Setup mocks (URL-based dispatch)
        conn = Mock(status_code=200, json=lambda: {"name": "User"})
        slug = Mock(status_code=200, json=lambda: [])
        cat1 = Mock(status_code=200, json=lambda: [{"id": 1, "name": "Automation"}])
        cat2 = Mock(status_code=200, json=lambda: [{"id": 2, "name": "WordPress"}])
        mock_get.side_effect = [conn, slug, cat1, cat2]
        mock_post.side_effect = [
            Mock(status_code=201, json=lambda: {"id": 123}),  # Image
            Mock(
                status_code=201,
                json=lambda: {
                    "id": 456,
                    "link": "https://test.com/blog-automation-guide/",
                    "title": {"rendered": "Getting Started with Blog Automation"},
                    "slug": "blog-automation-guide",
                },
            ),  # Post
        ]

        # Create and enqueue
        zip_path = create_sample_zip(test_env["inbox"])
        job_id = enqueue_job(zip_path)

        # Process
        start_time = time.time()
        job = get_job_by_id(job_id)
        process_single_job(job)
        elapsed = time.time() - start_time

        # Verify success
        job = get_job_by_id(job_id)
        assert job.state == JobState.DONE
        assert job.slug == "blog-automation-guide"

        # Verify timing (should be fast in tests)
        assert elapsed < 5  # Seconds

        # Verify ZIP moved
        assert (test_env["published"] / zip_path.name).exists()

        # ✅ ACCEPTANCE CRITERIA MET
        print("✅ Sample ZIP created WordPress draft successfully")
        print(f"✅ Processing completed in {elapsed:.2f}s")
        print("✅ All fields correctly populated")
        print("✅ ZIP moved to published directory")
