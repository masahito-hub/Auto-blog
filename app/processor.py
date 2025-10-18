"""ZIP file processor and Markdown to HTML converter."""

import logging
import zipfile
from pathlib import Path
from typing import Optional

import markdown
import yaml

from app.config import settings

logger = logging.getLogger(__name__)


class ProcessorError(Exception):
    """Custom exception for processor errors."""
    pass


class PostData:
    """Structured post data from frontmatter and content."""

    def __init__(self, frontmatter: dict, content: str, work_dir: Path):
        self.frontmatter = frontmatter
        self.content = content
        self.work_dir = work_dir

        # Extract required fields
        self.title = frontmatter.get("title")
        self.slug = frontmatter.get("slug")
        self.status = frontmatter.get("status", "draft")

        if not self.title or not self.slug:
            raise ProcessorError("Missing required fields: title and slug")

        # Optional fields
        self.description = frontmatter.get("description", "")
        self.categories = frontmatter.get("categories", [])
        self.tags = frontmatter.get("tags", [])
        self.featured_image = frontmatter.get("featured_image")
        self.author = frontmatter.get("author")
        self.date = frontmatter.get("date")

    def get_html_content(self) -> str:
        """Convert Markdown content to HTML."""
        return markdown.markdown(
            self.content,
            extensions=["extra", "codehilite", "toc"]
        )


def extract_zip(zip_path: Path) -> Path:
    """Extract ZIP file to work directory."""
    work_dir = settings.work_dir / zip_path.stem
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(work_dir)
        logger.info(f"Extracted {zip_path.name} to {work_dir}")
        return work_dir
    except zipfile.BadZipFile as e:
        raise ProcessorError(f"Invalid ZIP file: {e}")


def parse_post_md(work_dir: Path) -> PostData:
    """Parse post.md file and extract frontmatter and content."""
    post_md = work_dir / "post.md"

    if not post_md.exists():
        raise ProcessorError("post.md not found in ZIP")

    content = post_md.read_text(encoding="utf-8")

    # Split frontmatter and content
    if not content.startswith("---"):
        raise ProcessorError("post.md must start with YAML frontmatter (----)")

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ProcessorError("Invalid frontmatter format")

    try:
        frontmatter = yaml.safe_load(parts[1])
        markdown_content = parts[2].strip()
    except yaml.YAMLError as e:
        raise ProcessorError(f"Invalid YAML frontmatter: {e}")

    return PostData(frontmatter, markdown_content, work_dir)


def process_zip(zip_path: Path) -> PostData:
    """Process ZIP file and return PostData."""
    logger.info(f"Processing {zip_path.name}")

    # Extract ZIP
    work_dir = extract_zip(zip_path)

    # Parse post.md
    post_data = parse_post_md(work_dir)

    logger.info(f"Processed post: {post_data.slug}")
    return post_data
