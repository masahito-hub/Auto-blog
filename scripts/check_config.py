#!/usr/bin/env python3
"""Configuration validation script.

Run this script to verify your environment is properly configured
before starting the Blog Pipeline service.

Usage:
    python scripts/check_config.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from requests.auth import HTTPBasicAuth

from app.config import settings


def print_check(message: str, passed: bool):
    """Print check result with color."""
    icon = "✅" if passed else "❌"
    print(f"{icon} {message}")
    return passed


def check_config_loaded():
    """Check if configuration loaded successfully."""
    try:
        _ = settings.wp_base_url
        return print_check("Configuration loaded successfully", True)
    except Exception as e:
        return print_check(f"Configuration error: {e}", False)


def check_wordpress_url():
    """Check WordPress URL format."""
    url = settings.wp_base_url
    valid = url.startswith(("http://", "https://"))
    return print_check(f"WordPress URL is valid: {url}", valid)


def check_wordpress_api():
    """Check if WordPress REST API is accessible."""
    try:
        response = requests.get(
            f"{settings.wp_base_url}/wp-json/",
            timeout=10
        )
        accessible = response.status_code == 200
        if not accessible:
            print(f"   Response: {response.status_code}")
        return print_check("WordPress REST API is accessible", accessible)
    except requests.RequestException as e:
        print(f"   Error: {e}")
        return print_check("WordPress REST API is accessible", False)


def check_wordpress_auth():
    """Check WordPress authentication."""
    try:
        auth = HTTPBasicAuth(settings.wp_user, settings.wp_app_password)
        response = requests.get(
            f"{settings.wp_base_url}/wp-json/wp/v2/users/me",
            auth=auth,
            timeout=10
        )
        authenticated = response.status_code == 200
        if not authenticated:
            print(f"   Response: {response.status_code}")
            if response.status_code == 401:
                print("   Hint: Check your WP_USER and WP_APP_PASSWORD")
        return print_check("WordPress authentication successful", authenticated)
    except requests.RequestException as e:
        print(f"   Error: {e}")
        return print_check("WordPress authentication successful", False)


def check_wordpress_posts_permission():
    """Check if user can create posts."""
    try:
        auth = HTTPBasicAuth(settings.wp_user, settings.wp_app_password)
        response = requests.options(
            f"{settings.wp_base_url}/wp-json/wp/v2/posts",
            auth=auth,
            timeout=10
        )
        # Check if POST method is allowed
        allowed_methods = response.headers.get("Allow", "")
        can_post = "POST" in allowed_methods or response.status_code == 200
        if not can_post:
            print(f"   Allowed methods: {allowed_methods}")
            print("   Hint: User needs Editor or Administrator role")
        return print_check("Can create posts (permissions OK)", can_post)
    except requests.RequestException as e:
        print(f"   Error: {e}")
        return print_check("Can create posts (permissions OK)", False)


def check_wordpress_media_permission():
    """Check if user can upload media."""
    try:
        auth = HTTPBasicAuth(settings.wp_user, settings.wp_app_password)
        response = requests.options(
            f"{settings.wp_base_url}/wp-json/wp/v2/media",
            auth=auth,
            timeout=10
        )
        allowed_methods = response.headers.get("Allow", "")
        can_upload = "POST" in allowed_methods or response.status_code == 200
        if not can_upload:
            print(f"   Allowed methods: {allowed_methods}")
        return print_check("Can upload media (permissions OK)", can_upload)
    except requests.RequestException as e:
        print(f"   Error: {e}")
        return print_check("Can upload media (permissions OK)", False)


def check_directories():
    """Check if required directories exist and are writable."""
    all_ok = True
    for name, path in [
        ("inbox", settings.inbox_dir),
        ("work", settings.work_dir),
        ("published", settings.published_dir),
    ]:
        exists = path.exists()
        writable = path.exists() and path.is_dir()
        
        if not writable:
            print(f"   {name}: {path}")
            all_ok = False
    
    return print_check("All directories are writable", all_ok)


def check_slack():
    """Check Slack webhook (optional)."""
    if not settings.slack_webhook_url:
        print("ℹ️  Slack webhook not configured (optional)")
        return True
    
    try:
        response = requests.post(
            settings.slack_webhook_url,
            json={"text": "Blog Pipeline configuration test"},
            timeout=10
        )
        works = response.status_code == 200
        if not works:
            print(f"   Response: {response.status_code}")
        return print_check("Slack webhook is configured (optional)", works)
    except requests.RequestException as e:
        print(f"   Error: {e}")
        return print_check("Slack webhook is configured (optional)", False)


def main():
    """Run all configuration checks."""
    print("\n🔍 Blog Pipeline Configuration Check\n")
    print("=" * 50)
    
    checks = [
        check_config_loaded(),
        check_wordpress_url(),
        check_wordpress_api(),
        check_wordpress_auth(),
        check_wordpress_posts_permission(),
        check_wordpress_media_permission(),
        check_directories(),
        check_slack(),
    ]
    
    print("\n" + "=" * 50)
    
    if all(checks):
        print("\n🎉 All checks passed! Your environment is ready.\n")
        print("Next steps:")
        print("  1. Create a test ZIP file (see docs/SETUP.md)")
        print("  2. Run: python -m app.server")
        print("  3. Drop ZIP in var/inbox/")
        print("  4. Check WordPress for your draft post")
        return 0
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.\n")
        print("Troubleshooting:")
        print("  - Check .env file exists and is properly formatted")
        print("  - Verify WordPress Application Password")
        print("  - Ensure WordPress REST API is enabled")
        print("  - See docs/SETUP.md for detailed instructions")
        return 1


if __name__ == "__main__":
    sys.exit(main())
