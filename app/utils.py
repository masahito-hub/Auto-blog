"""Common utilities for logging and notifications."""

import logging

import requests
from requests.exceptions import RequestException, Timeout

from app.config import settings

logger = logging.getLogger(__name__)


def notify_slack(message: str, success: bool = True):
    """Send notification to Slack.

    Args:
        message: Notification message
        success: Whether this is a success (True) or failure (False) notification
    """
    if not settings.slack_webhook_url:
        logger.debug("Slack webhook not configured, skipping notification")
        return

    # Determine color and emoji
    if success:
        color = "good"  # Green
        emoji = "✅"
    else:
        color = "danger"  # Red
        emoji = "❌"

    # Build Slack message payload
    payload = {
        "attachments": [
            {
                "color": color,
                "text": f"{emoji} {message}",
                "footer": "Blog Pipeline",
                "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
                "ts": int(__import__("time").time()),
            }
        ]
    }

    try:
        response = requests.post(settings.slack_webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            logger.debug(f"Slack notification sent: {message[:50]}...")
        else:
            logger.warning(
                f"Slack notification failed: {response.status_code} - {response.text[:100]}"
            )

    except Timeout:
        logger.warning("Slack notification timeout (ignoring)")
    except RequestException as e:
        logger.warning(f"Failed to send Slack notification: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error sending Slack notification: {e}")


def format_error_for_notification(error: Exception, context: str | None = None) -> str:
    """Format error message for user-friendly notification.

    Args:
        error: Exception to format
        context: Optional context string

    Returns:
        Formatted error message
    """
    error_msg = str(error)

    # Truncate very long errors
    if len(error_msg) > 200:
        error_msg = error_msg[:200] + "..."

    if context:
        return f"{context}: {error_msg}"

    return error_msg


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to append if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix
