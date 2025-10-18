"""Tests for processor module."""

import zipfile
from pathlib import Path

import pytest

from app.processor import (
    PostData,
    ProcessorError,
    cleanup_work_dir,
    extract_zip,
    parse_post_md,
    process_zip,
    validate_zip_path_safety,
)


def create_test_zip(path: Path, content: dict):
    """Helper to create test ZIP files.
    
    Args:
        path: Output ZIP path
        content: Dictionary of {filename: content}
    """
    with zipfile.ZipFile(path, 'w') as zip_ref:
        for filename, file_content in content.items():
            zip_ref.writestr(filename, file_content)


@pytest.fixture
def temp_dirs(tmp_path, monkeypatch):
    """Create temporary directories for testing."""
    from app import config
    
    inbox = tmp_path / "inbox"
    work = tmp_path / "work"
    published = tmp_path / "published"
    
    inbox.mkdir()
    work.mkdir()
    published.mkdir()
    
    monkeypatch.setattr(config.settings, "inbox_dir", inbox)
    monkeypatch.setattr(config.settings, "work_dir", work)
    monkeypatch.setattr(config.settings, "published_dir", published)
    
    return {"inbox": inbox, "work": work, "published": published}


def test_validate_zip_path_safety(tmp_path):
    """Test ZIP path validation."""
    # Valid paths
    validate_zip_path_safety(tmp_path, "post.md")
    validate_zip_path_safety(tmp_path, "images/hero.jpg")
    validate_zip_path_safety(tmp_path, "subdir/file.txt")
    
    # Invalid paths
    with pytest.raises(ProcessorError, match="Unsafe path"):
        validate_zip_path_safety(tmp_path, "../etc/passwd")
    
    with pytest.raises(ProcessorError, match="Unsafe path"):
        validate_zip_path_safety(tmp_path, "/etc/passwd")


def test_extract_valid_zip(temp_dirs):
    """Test extracting a valid ZIP file."""
    zip_path = temp_dirs["inbox"] / "test.zip"
    create_test_zip(zip_path, {
        "post.md": "---\ntitle: Test\nslug: test\n---\nContent",
        "images/hero.jpg": b"fake image data",
    })
    
    work_dir = extract_zip(zip_path)
    
    assert work_dir.exists()
    assert (work_dir / "post.md").exists()
    assert (work_dir / "images" / "hero.jpg").exists()


def test_extract_invalid_zip(temp_dirs):
    """Test extracting an invalid ZIP."""
    zip_path = temp_dirs["inbox"] / "invalid.zip"
    zip_path.write_text("not a zip file")
    
    with pytest.raises(ProcessorError, match="Invalid ZIP"):
        extract_zip(zip_path)


def test_parse_valid_frontmatter(temp_dirs):
    """Test parsing valid post.md with frontmatter."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    
    content = """---
title: "Test Post"
slug: "test-post"
description: "A test post"
status: "draft"
categories: ["Category1"]
tags: ["tag1", "tag2"]
featured_image: "images/hero.jpg"
---

# Heading

This is the **body** content.
"""
    
    (work_dir / "post.md").write_text(content)
    
    post_data = parse_post_md(work_dir)
    
    assert post_data.title == "Test Post"
    assert post_data.slug == "test-post"
    assert post_data.description == "A test post"
    assert post_data.status == "draft"
    assert post_data.categories == ["Category1"]
    assert post_data.tags == ["tag1", "tag2"]
    assert post_data.featured_image == "images/hero.jpg"
    assert "This is the **body** content" in post_data.content


def test_parse_missing_required_fields(temp_dirs):
    """Test that missing required fields raise error."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    
    # Missing slug
    content = """---
title: "Test Post"
---

Content here.
"""
    
    (work_dir / "post.md").write_text(content)
    
    with pytest.raises(ProcessorError, match="Missing required field: slug"):
        parse_post_md(work_dir)


def test_parse_no_frontmatter(temp_dirs):
    """Test parsing post.md without frontmatter."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    
    (work_dir / "post.md").write_text("Just content, no frontmatter")
    
    with pytest.raises(ProcessorError, match="must start with YAML frontmatter"):
        parse_post_md(work_dir)


def test_parse_invalid_yaml(temp_dirs):
    """Test parsing invalid YAML frontmatter."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    
    content = """---
title: "Test
slug: [invalid: yaml
---

Content
"""
    
    (work_dir / "post.md").write_text(content)
    
    with pytest.raises(ProcessorError, match="Invalid YAML"):
        parse_post_md(work_dir)


def test_parse_invalid_slug(temp_dirs):
    """Test that invalid slug formats are rejected."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    
    # Uppercase not allowed
    content = """---
title: "Test"
slug: "Test-Post"
---
Content
"""
    
    (work_dir / "post.md").write_text(content)
    
    with pytest.raises(ProcessorError, match="Invalid slug format"):
        parse_post_md(work_dir)


def test_html_conversion():
    """Test Markdown to HTML conversion."""
    frontmatter = {
        "title": "Test",
        "slug": "test",
    }
    content = """# Heading

Paragraph with **bold** and *italic* text.

- List item 1
- List item 2

```python
print("code block")
```
"""
    
    post_data = PostData(frontmatter, content, Path("/tmp"))
    html = post_data.get_html_content()
    
    assert "<h1>Heading</h1>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<li>List item 1</li>" in html
    assert "<code" in html


def test_get_featured_image_path(temp_dirs):
    """Test getting featured image path."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    (work_dir / "images").mkdir()
    (work_dir / "images" / "hero.jpg").write_bytes(b"fake")
    
    frontmatter = {
        "title": "Test",
        "slug": "test",
        "featured_image": "images/hero.jpg",
    }
    
    post_data = PostData(frontmatter, "Content", work_dir)
    image_path = post_data.get_featured_image_path()
    
    assert image_path is not None
    assert image_path.exists()
    assert image_path.name == "hero.jpg"


def test_get_image_files(temp_dirs):
    """Test getting all image files."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    images_dir = work_dir / "images"
    images_dir.mkdir()
    
    # Create test images
    (images_dir / "img1.jpg").write_bytes(b"fake1")
    (images_dir / "img2.png").write_bytes(b"fake2")
    (images_dir / "img3.gif").write_bytes(b"fake3")
    (images_dir / "not-image.txt").write_text("text")
    
    frontmatter = {"title": "Test", "slug": "test"}
    post_data = PostData(frontmatter, "Content", work_dir)
    
    images = post_data.get_image_files()
    
    assert len(images) == 3
    assert all(img.suffix.lower() in ['.jpg', '.png', '.gif'] for img in images)


def test_process_zip_complete_workflow(temp_dirs):
    """Test complete ZIP processing workflow."""
    zip_path = temp_dirs["inbox"] / "complete-test.zip"
    
    create_test_zip(zip_path, {
        "post.md": """---
title: "Complete Test"
slug: "complete-test"
description: "Testing complete workflow"
---

# Introduction

This is a **complete** test.
""",
        "images/hero.jpg": b"fake hero image",
        "images/diagram.png": b"fake diagram",
    })
    
    post_data = process_zip(zip_path)
    
    assert post_data.title == "Complete Test"
    assert post_data.slug == "complete-test"
    assert "complete" in post_data.content.lower()
    
    # Check images were found
    images = post_data.get_image_files()
    assert len(images) == 2


def test_cleanup_work_dir(temp_dirs):
    """Test work directory cleanup."""
    work_dir = temp_dirs["work"] / "test"
    work_dir.mkdir()
    (work_dir / "file.txt").write_text("test")
    
    assert work_dir.exists()
    
    cleanup_work_dir(work_dir)
    
    assert not work_dir.exists()
