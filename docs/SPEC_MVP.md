# MVP Specification: Blog Pipeline

## Overview
**Goal:** Automate WordPress draft creation from ZIP files containing Markdown posts with images.

**Workflow:**
1. Drop ZIP file into `var/inbox/`
2. System extracts, parses frontmatter + Markdown
3. Uploads images to WordPress media library
4. Creates draft post with featured image
5. Moves ZIP to `var/published/` on success

## MVP Scope (In Scope)
- ✅ ZIP file monitoring via `watchdog`
- ✅ YAML frontmatter parsing (required: `title`, `slug`)
- ✅ Markdown → HTML conversion
- ✅ Image upload (existing images only, no AI generation)
- ✅ WordPress REST API integration (`/wp/v2/posts`, `/wp/v2/media`)
- ✅ Draft status only
- ✅ SQLite-based job queue with exponential backoff retry (1m → 5m → 15m → 1h → 6h)
- ✅ FastAPI monitoring endpoints: `/health`, `/status`, `/retry`
- ✅ Slack notifications (success/failure)
- ✅ systemd service for production deployment

## Out of Scope (Future Iterations)
- ❌ AI image generation (`{image: ...}` tags)
- ❌ Auto-create categories/tags if missing
- ❌ Theme-specific configuration (YAML profiles)
- ❌ Publish status (draft → publish automation)
- ❌ Git commit tracking

## Input Format

### ZIP Structure
```
<slug>.zip
├── post.md          # YAML frontmatter + Markdown body (required)
└── images/          # Optional image directory
    ├── hero.jpg     # Referenced in frontmatter or content
    └── diagram.png
```

### Frontmatter Example
```yaml
---
project: "keto"              # Future theme identifier
title: "Keto Beginner's Guide"  # Required
slug: "keto-start-guide-001"    # Required
description: "7-day starter plan"  # Optional (used as excerpt)
status: "draft"              # Fixed to "draft" in MVP
categories: ["Ketogenic"]    # Optional (must exist in WP)
tags: ["low-carb", "meal-prep"]  # Optional (must exist in WP)
featured_image: "images/hero.jpg"  # Optional
author: "Editorial Team"     # Optional
date: "2025-10-05"           # Optional
---

# Your Markdown Content Here
Introduction paragraph...

## Section 1
Detailed content...
```

## Architecture

### Components
1. **Watcher** (`app/watcher.py`) - Monitors `var/inbox/` for new ZIPs
2. **Processor** (`app/processor.py`) - Extracts ZIP, parses frontmatter, converts Markdown
3. **Publisher** (`app/publisher.py`) - Uploads images & creates WP posts
4. **Queue** (`app/queue.py`) - SQLite-based job queue with retry logic
5. **Server** (`app/server.py`) - FastAPI endpoints for monitoring
6. **Utils** (`app/utils.py`) - Slack notifications, logging

### Job States
- `queued` → `running` → `done` | `failed`
- Failed jobs retry with exponential backoff (max 5 attempts)

### Retry Strategy
| Attempt | Delay   |
|---------|--------|
| 1       | 1 min  |
| 2       | 5 min  |
| 3       | 15 min |
| 4       | 1 hour |
| 5       | 6 hours|

## API Endpoints

### `GET /health`
Returns system health status.
```json
{"ok": true, "version": "0.1.0"}
```

### `GET /status?limit=50`
Returns recent job history.
```json
{
  "jobs": [
    {
      "id": 123,
      "file": "keto-guide-001.zip",
      "slug": "keto-start-guide-001",
      "state": "done",
      "attempts": 1,
      "last_error": null,
      "updated_at": "2025-10-06T10:30:00"
    }
  ],
  "stats": {
    "queued": 2,
    "running": 1,
    "done": 45,
    "failed": 3
  }
}
```

### `POST /retry`
Manually retry a failed job.
```json
{"job_id": 123}
```

## Environment Variables
```bash
# WordPress
WP_BASE_URL=https://example.com
WP_USER=editor_user
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Slack (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ

# Image Generation (MVP: disabled)
IMAGES_PROVIDER=none
```

## Acceptance Criteria
✅ Sample ZIP placed in `var/inbox/` creates WP draft within 60 seconds  
✅ Post title, slug, content, and featured image correctly set  
✅ `/health` returns 200  
✅ `/status` shows job in `done` state  
✅ Failed jobs trigger Slack notification and auto-retry  
✅ Successful jobs move ZIP to `var/published/`  

## Security Considerations
- `.env` file permissions: `chmod 600`
- No secrets in logs or error messages
- ZIP extraction validates file paths (no `../` traversal)
- WordPress Application Password with minimal permissions

## Testing Plan
1. **Happy Path**: Valid ZIP → Draft created → Slack success notification
2. **Invalid ZIP**: Corrupt file → Failed state → Slack error notification
3. **Missing Required Fields**: No `title` → Validation error → Failed state
4. **Retry Logic**: Simulate WP API timeout → Auto-retry with backoff
5. **Manual Retry**: Use `/retry` endpoint to reprocess failed job

## Deployment

### Installation
```bash
# Setup directories
sudo mkdir -p /opt/blog-pipeline
cd /opt/blog-pipeline

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with actual credentials
chmod 600 .env

# Install systemd service
sudo cp systemd/blog-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable blog-pipeline
sudo systemctl start blog-pipeline
```

### Monitoring
```bash
# Check service status
sudo systemctl status blog-pipeline

# View logs
journalctl -u blog-pipeline -f

# Check health endpoint
curl http://localhost:8000/health

# View job queue
curl http://localhost:8000/status
```

## Future Roadmap (Post-MVP)
- **P2**: Theme YAML configs for category/tag management
- **P3**: AI image generation with `{image: ...}` tag replacement
- **P4**: Auto-publish workflow + public URL notifications
- **P5**: Git integration (commit published content)
- **P6**: Prometheus metrics endpoint
