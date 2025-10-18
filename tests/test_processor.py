"""Tests for processor module."""

import pytest
from pathlib import Path

from app.processor import PostData, parse_post_md, ProcessorError


def test_parse_valid_frontmatter(tmp_path):
    """Test parsing valid post.md with frontmatter."""
    content = """---
title: "Test Post"
slug: "test-post"
description: "A test post"
status: "draft"
---

# Content
This is the body.
"""
    
    post_md = tmp_path / "post.md"
    post_md.write_text(content)
    
    post_data = parse_post_md(tmp_path)
    
    assert post_data.title == "Test Post"
    assert post_data.slug == "test-post"
    assert post_data.status == "draft"
    assert "This is the body" in post_data.content


def test_parse_missing_required_field(tmp_path):
    """Test that missing required fields raise error."""
    content = """---
title: "Test Post"
---

Content here.
"""
    
    post_md = tmp_path / "post.md"
    post_md.write_text(content)
    
    with pytest.raises(ProcessorError, match="Missing required fields"):
        parse_post_md(tmp_path)


def test_html_conversion():
    """Test Markdown to HTML conversion."""
    frontmatter = {
        "title": "Test",
        "slug": "test",
    }
    content = "# Heading\n\nParagraph with **bold** text."
    
    post_data = PostData(frontmatter, content, Path("/tmp"))
    html = post_data.get_html_content()
    
    assert "<h1>" in html
    assert "<strong>bold</strong>" in html
