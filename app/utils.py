"""Common utilities for logging and notifications."""

import logging
from typing import Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def notify_slack(message: str, success: bool = True):
    """Send notification to Slack."""
    if not settings.slack_webhook_url:
        logger.debug("Slack webhook not configured, skipping notification")
        return

    color = "good" if success else "danger"
    emoji = "✅" if success else "❌"

    payload = {
        "attachments": [
            {
                "color": color,
                "text": f"{emoji} {message}",
                "footer": "Blog Pipeline",
            }
        ]
    }

    try:
        response = requests.post(
            settings.slack_webhook_url,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        logger.debug("Slack notification sent")
    except requests.RequestException as e:
        logger.warning(f"Failed to send Slack notification: {e}")
