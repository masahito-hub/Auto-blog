"""Tests for publisher module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from app.processor import PostData
from app.publisher import PublisherError, WordPressPublisher, publish_post


@pytest.fixture
def mock_post_data(tmp_path):
    """Create mock PostData for testing."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    
    frontmatter = {
        "title": "Test Post",
        "slug": "test-post",
        "description": "Test description",
        "status": "draft",
    }
    
    content = "# Test Content\n\nThis is a test post."
    
    return PostData(frontmatter, content, work_dir)


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    from app import config
    
    monkeypatch.setattr(config.settings, "wp_base_url", "https://test.com")
    monkeypatch.setattr(config.settings, "wp_user", "testuser")
    monkeypatch.setattr(config.settings, "wp_app_password", "testpassword")


def test_publisher_initialization(mock_settings):
    """Test WordPressPublisher initialization."""
    publisher = WordPressPublisher()
    
    assert publisher.base_url == "https://test.com"
    assert publisher.session.auth.username == "testuser"


@patch('app.publisher.requests.Session.get')
def test_test_connection_success(mock_get, mock_settings):
    """Test successful WordPress connection."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "Test User"}
    mock_get.return_value = mock_response
    
    publisher = WordPressPublisher()
    result = publisher.test_connection()
    
    assert result is True


@patch('app.publisher.requests.Session.get')
def test_test_connection_auth_failure(mock_get, mock_settings):
    """Test authentication failure."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response
    
    publisher = WordPressPublisher()
    
    with pytest.raises(PublisherError, match="authentication failed"):
        publisher.test_connection()


@patch('app.publisher.requests.Session.post')
def test_upload_media_success(mock_post, mock_settings, tmp_path):
    """Test successful media upload."""
    # Create test image
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(b"fake image data")
    
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": 123,
        "source_url": "https://test.com/wp-content/uploads/test.jpg",
        "mime_type": "image/jpeg",
    }
    mock_post.return_value = mock_response
    
    publisher = WordPressPublisher()
    media = publisher.upload_media(image_path)
    
    assert media["id"] == 123
    assert "source_url" in media


@patch('app.publisher.requests.Session.post')
def test_upload_media_file_not_found(mock_post, mock_settings):
    """Test uploading non-existent file."""
    publisher = WordPressPublisher()
    
    with pytest.raises(PublisherError, match="not found"):
        publisher.upload_media(Path("/nonexistent/image.jpg"))


@patch('app.publisher.requests.Session.post')
def test_upload_media_rate_limit(mock_post, mock_settings, tmp_path):
    """Test rate limit handling."""
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(b"fake")
    
    mock_response = Mock()
    mock_response.status_code = 429
    mock_post.return_value = mock_response
    
    publisher = WordPressPublisher()
    
    with pytest.raises(PublisherError, match="rate limit"):
        publisher.upload_media(image_path)


@patch('app.publisher.requests.Session.post')
def test_create_post_success(mock_post, mock_settings, mock_post_data):
    """Test successful post creation."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": 456,
        "link": "https://test.com/test-post/",
        "slug": "test-post",
    }
    mock_post.return_value = mock_response
    
    publisher = WordPressPublisher()
    post = publisher.create_post(mock_post_data, featured_media_id=123)
    
    assert post["id"] == 456
    assert "link" in post
    
    # Verify payload structure
    call_args = mock_post.call_args
    payload = call_args.kwargs["json"]
    assert payload["title"] == "Test Post"
    assert payload["slug"] == "test-post"
    assert payload["status"] == "draft"
    assert payload["featured_media"] == 123


@patch('app.publisher.requests.Session.post')
def test_create_post_without_featured_image(mock_post, mock_settings, mock_post_data):
    """Test post creation without featured image."""
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 456, "link": "https://test.com/test-post/"}
    mock_post.return_value = mock_response
    
    publisher = WordPressPublisher()
    post = publisher.create_post(mock_post_data)
    
    # Verify featured_media not in payload
    call_args = mock_post.call_args
    payload = call_args.kwargs["json"]
    assert "featured_media" not in payload


@patch('app.publisher.requests.Session.post')
def test_create_post_permission_denied(mock_post, mock_settings, mock_post_data):
    """Test permission denied error."""
    mock_response = Mock()
    mock_response.status_code = 403
    mock_post.return_value = mock_response
    
    publisher = WordPressPublisher()
    
    with pytest.raises(PublisherError, match="Permission denied"):
        publisher.create_post(mock_post_data)


def test_get_mime_type(mock_settings):
    """Test MIME type detection."""
    publisher = WordPressPublisher()
    
    assert publisher._get_mime_type(Path("test.jpg")) == "image/jpeg"
    assert publisher._get_mime_type(Path("test.png")) == "image/png"
    assert publisher._get_mime_type(Path("test.gif")) == "image/gif"
    assert publisher._get_mime_type(Path("test.webp")) == "image/webp"
    assert publisher._get_mime_type(Path("test.unknown")) == "application/octet-stream"


@patch('app.publisher.WordPressPublisher.test_connection')
@patch('app.publisher.WordPressPublisher.upload_media')
@patch('app.publisher.WordPressPublisher.create_post')
def test_publish_post_complete_workflow(
    mock_create_post,
    mock_upload_media,
    mock_test_connection,
    mock_settings,
    mock_post_data,
    tmp_path
):
    """Test complete publishing workflow."""
    # Setup featured image
    images_dir = mock_post_data.work_dir / "images"
    images_dir.mkdir()
    featured_img = images_dir / "hero.jpg"
    featured_img.write_bytes(b"fake")
    mock_post_data.featured_image = "images/hero.jpg"
    
    # Mock responses
    mock_test_connection.return_value = True
    mock_upload_media.return_value = {"id": 123}
    mock_create_post.return_value = {
        "id": 456,
        "link": "https://test.com/test-post/"
    }
    
    # Publish
    result = publish_post(mock_post_data)
    
    # Verify calls
    mock_test_connection.assert_called_once()
    mock_upload_media.assert_called_once()
    mock_create_post.assert_called_once()
    
    assert result["id"] == 456


@patch('app.publisher.WordPressPublisher.test_connection')
@patch('app.publisher.WordPressPublisher.create_post')
def test_publish_post_without_featured_image(
    mock_create_post,
    mock_test_connection,
    mock_settings,
    mock_post_data
):
    """Test publishing without featured image."""
    mock_test_connection.return_value = True
    mock_create_post.return_value = {"id": 456, "link": "https://test.com/test-post/"}
    
    result = publish_post(mock_post_data)
    
    # Should not attempt upload
    mock_create_post.assert_called_once()
    call_args = mock_create_post.call_args
    assert call_args.kwargs["featured_media_id"] is None


class TestSlugDuplicateCheck:
    """Test slug duplicate detection."""
    
    def test_check_slug_exists_returns_id(self, mock_settings):
        """Returns post ID when slug exists."""
        publisher = WordPressPublisher()
        with patch.object(publisher.session, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = [{"id": 123}]
            assert publisher.check_slug_exists("test") == 123
    
    def test_check_slug_exists_returns_none(self, mock_settings):
        """Returns None when slug does not exist."""
        publisher = WordPressPublisher()
        with patch.object(publisher.session, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = []
            assert publisher.check_slug_exists("test") is None


class TestCategoryResolution:
    """Test category resolution."""
    
    def test_resolve_missing_category_raises(self, mock_settings):
        """Raises error when category not found (fail-closed)."""
        publisher = WordPressPublisher()
        with patch.object(publisher.session, 'get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = []
            with pytest.raises(PublisherError):
                publisher.resolve_category_ids(["不明"])
