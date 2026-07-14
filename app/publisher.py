"""WordPress REST API publisher."""

import logging
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException, Timeout

from app.config import settings
from app.processor import PostData

logger = logging.getLogger(__name__)


class PublisherError(Exception):
    """Custom exception for publisher errors."""

    pass


class WordPressPublisher:
    """WordPress REST API client."""

    def __init__(self):
        """Initialize WordPress API client."""
        self.base_url = settings.wp_base_url.rstrip("/")
        self.auth = HTTPBasicAuth(settings.wp_user, settings.wp_app_password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update(
            {
                "User-Agent": "BlogPipeline/0.1.0",
            }
        )
        self.timeout = 30  # seconds

    def test_connection(self) -> bool:
        """Test connection to WordPress API.

        Returns:
            True if connection successful

        Raises:
            PublisherError: If connection fails
        """
        try:
            response = self.session.get(
                f"{self.base_url}/wp-json/wp/v2/users/me", timeout=self.timeout
            )

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"Connected to WordPress as: {user_data.get('name', 'unknown')}")
                return True
            elif response.status_code == 401:
                raise PublisherError(
                    "WordPress authentication failed. Check WP_USER and WP_APP_PASSWORD in .env"
                )
            else:
                raise PublisherError(
                    f"WordPress API returned {response.status_code}: {response.text}"
                )

        except Timeout:
            raise PublisherError(
                f"WordPress API timeout. Check if {self.base_url} is accessible."
            ) from None
        except RequestException as e:
            raise PublisherError(f"Failed to connect to WordPress: {e}") from e

    def _fetch_categories(self) -> dict:
        """Fetch all WordPress categories and cache them."""
        if hasattr(self, "_category_cache"):
            return self._category_cache

        categories = {}
        page = 1
        while True:
            response = self.session.get(
                f"{self.base_url}/wp-json/wp/v2/categories",
                params={"page": page, "per_page": 100},
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise PublisherError(f"Failed to fetch categories: {response.status_code}")
            data = response.json()
            if not data:
                break
            for cat in data:
                name = cat["name"]
                if name not in categories:
                    categories[name] = []
                categories[name].append(cat["id"])
            page += 1
            if len(data) < 100:
                break
        self._category_cache = categories
        return categories

    def resolve_category_ids(self, names: list) -> list:
        """Resolve category names to IDs (fail-closed, exact match)."""
        if not names:
            return []
        categories = self._fetch_categories()
        ids = []
        for name in names:
            matches = categories.get(name, [])
            if len(matches) == 0:
                raise PublisherError(f"Category not found: {name}")
            if len(matches) > 1:
                raise PublisherError(f"Multiple categories: {name}")
            ids.append(matches[0])
        return ids

    def check_slug_exists(self, slug: str) -> int | None:
        """Check slug exists (fail-closed)."""
        try:
            resp = self.session.get(
                f"{self.base_url}/wp-json/wp/v2/posts",
                params={"slug": slug, "status": "any"},
                timeout=self.timeout,
            )
        except Timeout:
            raise PublisherError("Timeout checking slug") from None
        except RequestException as e:
            raise PublisherError(f"Slug check failed: {e}") from e
        if resp.status_code != 200:
            raise PublisherError(f"Slug API error: {resp.status_code}")
        try:
            posts = resp.json()
        except Exception as e:
            raise PublisherError(f"Invalid JSON: {e}") from e
        if not posts:
            return None
        if len(posts) > 1:
            raise PublisherError(f"Multiple posts with slug '{slug}'")
        return posts[0]["id"]

    def upload_media(self, image_path: Path) -> dict:
        """Upload image to WordPress media library.

        Args:
            image_path: Path to image file

        Returns:
            Media object with 'id' and 'source_url'

        Raises:
            PublisherError: If upload fails
        """
        url = f"{self.base_url}/wp-json/wp/v2/media"

        # Validate file exists and size
        if not image_path.exists():
            raise PublisherError(f"Image file not found: {image_path}")

        file_size = image_path.stat().st_size
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise PublisherError(
                f"Image too large: {image_path.name} "
                f"({file_size / 1024 / 1024:.1f}MB > {max_size / 1024 / 1024}MB)"
            )

        try:
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, self._get_mime_type(image_path))}
                headers = {"Content-Disposition": f'attachment; filename="{image_path.name}"'}

                logger.debug(f"Uploading {image_path.name} ({file_size / 1024:.1f}KB)...")

                response = self.session.post(
                    url, files=files, headers=headers, timeout=self.timeout
                )

            # Handle response
            if response.status_code == 201:
                media = response.json()
                logger.info(
                    f"Uploaded {image_path.name} → ID: {media['id']} "
                    f"({media.get('mime_type', 'unknown')})"
                )
                return media
            elif response.status_code == 401:
                raise PublisherError("Authentication failed during image upload")
            elif response.status_code == 413:
                raise PublisherError(
                    f"Image too large for WordPress: {image_path.name}. "
                    "Check upload_max_filesize in WordPress settings."
                )
            elif response.status_code == 429:
                raise PublisherError("WordPress rate limit exceeded. Will retry later.")
            elif response.status_code >= 500:
                raise PublisherError(
                    f"WordPress server error ({response.status_code}). Will retry."
                )
            else:
                raise PublisherError(
                    f"Failed to upload {image_path.name}: "
                    f"{response.status_code} - {response.text[:200]}"
                )

        except Timeout:
            raise PublisherError(
                f"Timeout uploading {image_path.name}. File may be too large or connection is slow."
            ) from None
        except RequestException as e:
            raise PublisherError(f"Failed to upload {image_path.name}: {e}") from e

    def _validate_image_path(self, work_dir: Path, rel_path: str) -> Path:
        """Validate image path (fail-closed)."""
        if not rel_path.startswith("images/"):
            raise PublisherError(f"Image must be under images/: {rel_path}")
        if ".." in rel_path:
            raise PublisherError(f"Path traversal not allowed: {rel_path}")
        img_path = (work_dir / rel_path).resolve()
        if not str(img_path).startswith(str(work_dir.resolve())):
            raise PublisherError(f"Path escape: {rel_path}")
        if img_path.is_symlink():
            raise PublisherError(f"Symlink not allowed: {rel_path}")
        if not img_path.exists():
            raise PublisherError(f"Image not found: {rel_path}")
        return img_path

    def upload_content_images(self, post_data: PostData) -> PostData:
        """Upload content images and replace paths with URLs."""
        import re

        content = post_data.content
        pattern = r"!\[([^\]]*)\]\((images/[^)]+)\)"
        matches = re.findall(pattern, content)
        if not matches:
            return post_data
        uploaded = {}  # dedupe: rel_path -> url
        for alt, rel_path in matches:
            if rel_path in uploaded:
                url = uploaded[rel_path]
            else:
                img_path = self._validate_image_path(post_data.work_dir, rel_path)
                media = self.upload_media(img_path)
                url = media["source_url"]
                uploaded[rel_path] = url
            old_ref = f"![{alt}]({rel_path})"
            new_ref = f"![{alt}]({url})"
            content = content.replace(old_ref, new_ref)
        post_data.content = content
        return post_data

    def create_post(self, post_data: PostData, featured_media_id: int | None = None) -> dict:
        """Create WordPress post as draft.

        Args:
            post_data: PostData object
            featured_media_id: WordPress media ID for featured image

        Returns:
            WordPress post object with 'id' and 'link'

        Raises:
            PublisherError: If post creation fails
        """
        # Check for duplicate slug (fail-closed for idempotency)
        existing_id = self.check_slug_exists(post_data.slug)
        if existing_id:
            raise PublisherError(
                f"Post with slug '{post_data.slug}' already exists (ID: {existing_id}). "
                "Delete or rename the existing post first."
            )

        url = f"{self.base_url}/wp-json/wp/v2/posts"

        # Build payload
        payload = {
            "title": post_data.title,
            "slug": post_data.slug,
            "content": post_data.get_html_content(),
            "excerpt": post_data.description,
            "status": "draft",  # Always force draft for safety
        }

        if featured_media_id:
            payload["featured_media"] = featured_media_id

        # Resolve category names to WordPress IDs (fail-closed)
        if post_data.categories:
            category_ids = self.resolve_category_ids(post_data.categories)
            payload["categories"] = category_ids

        # Tags not implemented yet
        if post_data.tags:
            logger.debug(f"Tags (not implemented): {post_data.tags}")

        try:
            logger.debug(f"Creating post: {post_data.slug}...")

            response = self.session.post(url, json=payload, timeout=self.timeout)

            # Handle response
            if response.status_code == 201:
                post = response.json()
                logger.info(f"Created post → ID: {post['id']} | {post['link']}")
                return post
            elif response.status_code == 401:
                raise PublisherError("Authentication failed during post creation")
            elif response.status_code == 403:
                raise PublisherError("Permission denied. User needs Editor or Administrator role.")
            elif response.status_code == 429:
                raise PublisherError("WordPress rate limit exceeded. Will retry later.")
            elif response.status_code >= 500:
                raise PublisherError(
                    f"WordPress server error ({response.status_code}). Will retry."
                )
            else:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else {}
                )
                error_msg = error_data.get("message", response.text[:200])
                raise PublisherError(f"Failed to create post: {response.status_code} - {error_msg}")

        except Timeout:
            raise PublisherError(
                f"Timeout creating post: {post_data.slug}. "
                "Content may be too large or connection is slow."
            ) from None
        except RequestException as e:
            raise PublisherError(f"Failed to create post: {e}") from e

    def _get_mime_type(self, path: Path) -> str:
        """Get MIME type from file extension.

        Args:
            path: File path

        Returns:
            MIME type string
        """
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(path.suffix.lower(), "application/octet-stream")


def publish_post(post_data: PostData) -> dict:
    """Publish post to WordPress.

    This is the main entry point for publishing.

    Args:
        post_data: PostData object from processor

    Returns:
        WordPress post object with 'id' and 'link'

    Raises:
        PublisherError: If publishing fails
    """
    publisher = WordPressPublisher()

    # Test connection first
    publisher.test_connection()

    # Upload featured image if specified
    featured_media_id = None
    featured_image_path = post_data.get_featured_image_path()

    if featured_image_path:
        try:
            media = publisher.upload_media(featured_image_path)
            featured_media_id = media["id"]
        except PublisherError as e:
            # Log warning but continue (post can exist without featured image)
            logger.warning(f"Failed to upload featured image: {e}")
    elif post_data.featured_image:
        logger.warning(f"Featured image specified but not found: {post_data.featured_image}")

    # Upload content images (fail on error)
    post_data = publisher.upload_content_images(post_data)

    # Create post
    post = publisher.create_post(post_data, featured_media_id)

    return post
