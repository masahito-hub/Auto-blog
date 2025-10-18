"""ZIP file processor and Markdown to HTML converter."""

import logging
import shutil
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
        """Initialize PostData from frontmatter and content.
        
        Args:
            frontmatter: Parsed YAML frontmatter dictionary
            content: Markdown content (without frontmatter)
            work_dir: Working directory with extracted files
            
        Raises:
            ProcessorError: If required fields are missing
        """
        self.frontmatter = frontmatter
        self.content = content
        self.work_dir = work_dir

        # Extract required fields
        self.title = frontmatter.get("title")
        self.slug = frontmatter.get("slug")
        
        if not self.title:
            raise ProcessorError("Missing required field: title")
        if not self.slug:
            raise ProcessorError("Missing required field: slug")

        # Validate slug format (basic)
        if not self._is_valid_slug(self.slug):
            raise ProcessorError(
                f"Invalid slug format: {self.slug}. "
                "Use lowercase letters, numbers, and hyphens only."
            )

        # Optional fields with defaults
        self.status = frontmatter.get("status", "draft")
        self.description = frontmatter.get("description", "")
        self.categories = frontmatter.get("categories", [])
        self.tags = frontmatter.get("tags", [])
        self.featured_image = frontmatter.get("featured_image")
        self.author = frontmatter.get("author")
        self.date = frontmatter.get("date")
        self.project = frontmatter.get("project")  # For future theme support

        # Validate arrays
        if not isinstance(self.categories, list):
            self.categories = [self.categories] if self.categories else []
        if not isinstance(self.tags, list):
            self.tags = [self.tags] if self.tags else []

    def _is_valid_slug(self, slug: str) -> bool:
        """Validate slug format.
        
        Args:
            slug: Post slug to validate
            
        Returns:
            True if slug is valid
        """
        if not slug:
            return False
        
        # Allow lowercase letters, numbers, hyphens
        # Must start and end with alphanumeric
        import re
        pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
        return bool(re.match(pattern, slug))

    def get_html_content(self) -> str:
        """Convert Markdown content to HTML.
        
        Returns:
            HTML string
        """
        return markdown.markdown(
            self.content,
            extensions=[
                'extra',      # Tables, footnotes, etc.
                'codehilite',  # Syntax highlighting
                'toc',        # Table of contents
                'nl2br',      # Newline to <br>
            ],
            extension_configs={
                'codehilite': {
                    'linenums': False,
                    'guess_lang': False,
                }
            }
        )

    def get_featured_image_path(self) -> Optional[Path]:
        """Get absolute path to featured image.
        
        Returns:
            Path to featured image, or None if not specified or not found
        """
        if not self.featured_image:
            return None
        
        # Handle both absolute and relative paths
        if self.featured_image.startswith('/'):
            image_path = self.work_dir / self.featured_image.lstrip('/')
        else:
            image_path = self.work_dir / self.featured_image
        
        if not image_path.exists():
            logger.warning(f"Featured image not found: {self.featured_image}")
            return None
        
        return image_path

    def get_image_files(self) -> list[Path]:
        """Get all image files from work directory.
        
        Returns:
            List of image file paths
        """
        images_dir = self.work_dir / "images"
        if not images_dir.exists():
            return []
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        images = []
        
        for file in images_dir.iterdir():
            if file.is_file() and file.suffix.lower() in image_extensions:
                images.append(file)
        
        return sorted(images)  # Consistent ordering

    def __repr__(self):
        return f"<PostData slug={self.slug} title={self.title}>"


def validate_zip_path_safety(zip_path: Path, name: str):
    """Validate that ZIP member path is safe (no traversal attacks).
    
    Args:
        zip_path: Base extraction path
        name: ZIP member name
        
    Raises:
        ProcessorError: If path is unsafe
    """
    # Prevent path traversal
    if name.startswith('/') or '..' in name:
        raise ProcessorError(f"Unsafe path in ZIP: {name}")
    
    # Check resolved path is within work directory
    resolved = (zip_path / name).resolve()
    if not str(resolved).startswith(str(zip_path.resolve())):
        raise ProcessorError(f"Path traversal attempt: {name}")


def extract_zip(zip_path: Path) -> Path:
    """Extract ZIP file to work directory.
    
    Args:
        zip_path: Path to ZIP file
        
    Returns:
        Path to extraction directory
        
    Raises:
        ProcessorError: If ZIP is invalid or extraction fails
    """
    # Create work directory named after ZIP (without extension)
    work_dir = settings.work_dir / zip_path.stem
    
    # Clean up existing work directory if present
    if work_dir.exists():
        logger.warning(f"Work directory already exists, cleaning: {work_dir.name}")
        shutil.rmtree(work_dir)
    
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Validate all paths before extraction
            for name in zip_ref.namelist():
                validate_zip_path_safety(work_dir, name)
            
            # Extract all files
            zip_ref.extractall(work_dir)
        
        logger.info(f"Extracted {zip_path.name} to {work_dir.name}")
        return work_dir
        
    except zipfile.BadZipFile as e:
        raise ProcessorError(f"Invalid ZIP file: {e}")
    except Exception as e:
        # Clean up partial extraction
        if work_dir.exists():
            shutil.rmtree(work_dir)
        raise ProcessorError(f"Failed to extract ZIP: {e}")


def parse_post_md(work_dir: Path) -> PostData:
    """Parse post.md file and extract frontmatter and content.
    
    Args:
        work_dir: Directory containing extracted ZIP contents
        
    Returns:
        PostData object
        
    Raises:
        ProcessorError: If post.md is missing or invalid
    """
    # Look for post.md in root or one level deep
    post_md = work_dir / "post.md"
    
    if not post_md.exists():
        # Try to find it in subdirectories
        found = list(work_dir.rglob("post.md"))
        if found:
            post_md = found[0]
            logger.info(f"Found post.md at: {post_md.relative_to(work_dir)}")
        else:
            raise ProcessorError(
                "post.md not found in ZIP. "
                "Ensure your ZIP contains a post.md file in the root or a subdirectory."
            )

    try:
        content = post_md.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ProcessorError(
            "post.md must be UTF-8 encoded. "
            "Please save your file with UTF-8 encoding."
        )

    # Split frontmatter and content
    if not content.strip():
        raise ProcessorError("post.md is empty")
    
    if not content.startswith("---"):
        raise ProcessorError(
            "post.md must start with YAML frontmatter (---).\n"
            "Example:\n"
            "---\n"
            "title: \"My Post\"\n"
            "slug: \"my-post\"\n"
            "---\n"
            "\n"
            "Your content here..."
        )

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ProcessorError(
            "Invalid frontmatter format. "
            "Frontmatter must be enclosed in --- markers:\n"
            "---\n"
            "title: \"My Post\"\n"
            "---\n"
        )

    try:
        frontmatter = yaml.safe_load(parts[1])
        if frontmatter is None:
            frontmatter = {}
    except yaml.YAMLError as e:
        raise ProcessorError(f"Invalid YAML in frontmatter: {e}")

    markdown_content = parts[2].strip()
    
    if not markdown_content:
        logger.warning("Post has no content (only frontmatter)")

    return PostData(frontmatter, markdown_content, work_dir)


def cleanup_work_dir(work_dir: Path):
    """Clean up work directory after processing.
    
    Args:
        work_dir: Directory to clean up
    """
    if work_dir.exists():
        try:
            shutil.rmtree(work_dir)
            logger.debug(f"Cleaned up work directory: {work_dir.name}")
        except Exception as e:
            logger.warning(f"Failed to clean up {work_dir.name}: {e}")


def process_zip(zip_path: Path) -> PostData:
    """Process ZIP file and return PostData.
    
    This is the main entry point for processing a ZIP file.
    
    Args:
        zip_path: Path to ZIP file
        
    Returns:
        PostData object ready for publishing
        
    Raises:
        ProcessorError: If processing fails
    """
    logger.info(f"Processing {zip_path.name}")

    # Extract ZIP
    work_dir = extract_zip(zip_path)

    try:
        # Parse post.md
        post_data = parse_post_md(work_dir)
        logger.info(
            f"Processed post: slug={post_data.slug}, "
            f"images={len(post_data.get_image_files())}"
        )
        return post_data
        
    except Exception as e:
        # Clean up on failure
        cleanup_work_dir(work_dir)
        raise
