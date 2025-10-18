"""WordPress REST API publisher."""

import logging
from pathlib import Path
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

from app.config import settings
from app.processor import PostData

logger = logging.getLogger(__name__)


class PublisherError(Exception):
    """Custom exception for publisher errors."""
    pass


class WordPressPublisher:
    """WordPress REST API client."""

    def __init__(self):
        self.base_url = settings.wp_base_url.rstrip("/")
        self.auth = HTTPBasicAuth(settings.wp_user, settings.wp_app_password)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({"User-Agent": "BlogPipeline/0.1.0"})

    def upload_media(self, image_path: Path) -> int:
        """Upload image to WordPress media library."""
        url = f"{self.base_url}/wp-json/wp/v2/media"

        with open(image_path, "rb") as f:
            files = {
                "file": (image_path.name, f, self._get_mime_type(image_path))
            }
            headers = {"Content-Disposition": f'attachment; filename="{image_path.name}"'}

            response = self.session.post(url, files=files, headers=headers, timeout=30)

        if response.status_code not in (200, 201):
            raise PublisherError(
                f"Failed to upload {image_path.name}: {response.status_code} - {response.text}"
            )

        media_id = response.json()["id"]
        logger.info(f"Uploaded {image_path.name} -> ID: {media_id}")
        return media_id

    def create_post(self, post_data: PostData, featured_media_id: Optional[int] = None) -> dict:
        """Create WordPress post as draft."""
        url = f"{self.base_url}/wp-json/wp/v2/posts"

        payload = {
            "title": post_data.title,
            "slug": post_data.slug,
            "content": post_data.get_html_content(),
            "excerpt": post_data.description,
            "status": post_data.status,
        }

        if featured_media_id:
            payload["featured_media"] = featured_media_id

        # TODO: Add categories and tags (requires ID lookup)

        response = self.session.post(url, json=payload, timeout=30)

        if response.status_code not in (200, 201):
            raise PublisherError(
                f"Failed to create post: {response.status_code} - {response.text}"
            )

        post = response.json()
        logger.info(f"Created post: {post['link']}")
        return post

    def _get_mime_type(self, path: Path) -> str:
        """Get MIME type from file extension."""
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return mime_types.get(path.suffix.lower(), "application/octet-stream")


def publish_post(post_data: PostData) -> dict:
    """Publish post to WordPress."""
    publisher = WordPressPublisher()

    # Upload featured image if specified
    featured_media_id = None
    if post_data.featured_image:
        featured_path = post_data.work_dir / post_data.featured_image
        if featured_path.exists():
            try:
                featured_media_id = publisher.upload_media(featured_path)
            except PublisherError as e:
                logger.warning(f"Failed to upload featured image: {e}")

    # Create post
    post = publisher.create_post(post_data, featured_media_id)

    return post
