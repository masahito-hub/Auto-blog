"""Tests for watcher module."""

import time
import zipfile
from pathlib import Path

import pytest

from app.watcher import ZipFileHandler


@pytest.fixture
def temp_inbox(tmp_path, monkeypatch):
    """Create temporary inbox directory."""
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    
    # Mock settings
    from app import config
    monkeypatch.setattr(config.settings, "inbox_dir", inbox)
    monkeypatch.setattr(config.settings, "base_dir", tmp_path)
    
    # Initialize queue
    db_path = tmp_path / "queue.db"
    monkeypatch.setattr(config.settings, "db_path", db_path)
    
    from app.queue import init_db
    init_db()
    
    return inbox


def create_test_zip(path: Path, include_post_md: bool = True):
    """Create a test ZIP file."""
    with zipfile.ZipFile(path, 'w') as zip_ref:
        if include_post_md:
            zip_ref.writestr('post.md', '---\ntitle: Test\nslug: test\n---\nContent')
        zip_ref.writestr('test.txt', 'test content')


def test_validate_file_basic(temp_inbox):
    """Test basic file validation."""
    handler = ZipFileHandler()
    
    # Create valid file
    valid_file = temp_inbox / "valid.zip"
    create_test_zip(valid_file)
    
    assert handler._validate_file_basic(valid_file)
    
    # Empty file
    empty_file = temp_inbox / "empty.zip"
    empty_file.touch()
    
    assert not handler._validate_file_basic(empty_file)
    
    # Non-existent file
    assert not handler._validate_file_basic(temp_inbox / "missing.zip")


def test_validate_file_complete(temp_inbox):
    """Test complete file validation."""
    handler = ZipFileHandler()
    
    # Valid ZIP with post.md
    valid_file = temp_inbox / "valid.zip"
    create_test_zip(valid_file, include_post_md=True)
    
    assert handler._validate_file_complete(valid_file)
    
    # ZIP without post.md
    invalid_file = temp_inbox / "invalid.zip"
    create_test_zip(invalid_file, include_post_md=False)
    
    assert not handler._validate_file_complete(invalid_file)
    
    # Not a ZIP file
    not_zip = temp_inbox / "notzip.zip"
    not_zip.write_text("not a zip")
    
    assert not handler._validate_file_complete(not_zip)


def test_file_stability_check(temp_inbox):
    """Test file stability detection."""
    handler = ZipFileHandler()
    handler.stability_timeout = 1  # 1 second for testing
    
    test_file = temp_inbox / "test.zip"
    create_test_zip(test_file)
    
    # Simulate file detection
    info = {
        "detected_at": time.time(),
        "last_size": test_file.stat().st_size,
        "checked_count": 0,
    }
    
    # Should not be stable immediately
    assert not handler._is_file_stable(test_file, info)
    
    # Wait for stability timeout
    time.sleep(1.1)
    
    # Should be stable now
    assert handler._is_file_stable(test_file, info)


def test_on_created_event(temp_inbox):
    """Test file creation event handling."""
    handler = ZipFileHandler()
    
    test_file = temp_inbox / "test.zip"
    create_test_zip(test_file)
    
    class FakeEvent:
        def __init__(self, path, is_dir=False):
            self.src_path = str(path)
            self.is_directory = is_dir
    
    # Trigger creation event
    handler.on_created(FakeEvent(test_file))
    
    # File should be in pending
    assert str(test_file) in handler.pending_files
    
    # Directory should be ignored
    handler.on_created(FakeEvent(temp_inbox / "somedir", is_dir=True))
    assert len(handler.pending_files) == 1
    
    # Non-ZIP should be ignored
    txt_file = temp_inbox / "test.txt"
    txt_file.write_text("test")
    handler.on_created(FakeEvent(txt_file))
    assert len(handler.pending_files) == 1
