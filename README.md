# Blog Pipeline 🚀

**Automated WordPress publishing from ZIP archives**

Drop a ZIP file containing Markdown + images, and get a WordPress draft post automatically—no manual copy-pasting required.

## Features

✅ **Zero-friction publishing**: Just drop a ZIP in `var/inbox/`  
✅ **Markdown support**: Write in Markdown, publish as HTML  
✅ **Image handling**: Automatic upload to WordPress media library  
✅ **Robust retry logic**: Exponential backoff for failed jobs (1m → 6h)  
✅ **Monitoring API**: `/health`, `/status`, `/retry` endpoints  
✅ **Slack notifications**: Get notified on success/failure  
✅ **Production-ready**: systemd service with auto-restart  

## Quick Start

### Prerequisites
- Python 3.11+
- WordPress with Application Password enabled
- (Optional) Slack webhook for notifications

### Installation

```bash
# Clone repository
git clone https://github.com/masahito-hub/Auto-blog.git
cd Auto-blog

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your WordPress credentials
```

### Configuration

Edit `.env` with your credentials:

```bash
WP_BASE_URL=https://your-site.com
WP_USER=your_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx  # From WordPress → Users → Profile
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

### Usage

#### 1. Create a ZIP file

```
my-post.zip
├── post.md          # YAML frontmatter + Markdown
└── images/          # Optional
    └── hero.jpg
```

**Example `post.md`:**

```yaml
---
title: "Getting Started with Keto"
slug: "keto-start-guide"
description: "A beginner's guide to ketogenic diet"
status: "draft"
categories: ["Health"]
tags: ["keto", "nutrition"]
featured_image: "images/hero.jpg"
---

# Introduction

Your Markdown content here...
```

#### 2. Drop the ZIP

```bash
# Local development
cp my-post.zip var/inbox/

# Or via SSH
scp my-post.zip user@server:/opt/blog-pipeline/var/inbox/
```

#### 3. Monitor progress

```bash
# Check health
curl http://localhost:8000/health

# View job status
curl http://localhost:8000/status | jq

# Watch logs
python -m app.server  # Or: journalctl -u blog-pipeline -f
```

#### 4. Check WordPress

Your draft post will appear in **WordPress → Posts → Drafts** within ~60 seconds.

## API Endpoints

### `GET /health`
Health check endpoint.

```json
{"ok": true, "version": "0.1.0"}
```

### `GET /status?limit=50`
List recent jobs with status.

```json
{
  "jobs": [
    {
      "id": 1,
      "file": "my-post.zip",
      "slug": "keto-start-guide",
      "state": "done",
      "attempts": 1,
      "last_error": null,
      "updated_at": "2025-10-06T10:30:00"
    }
  ],
  "stats": {"queued": 0, "running": 1, "done": 45, "failed": 2}
}
```

### `POST /retry`
Manually retry a failed job.

```bash
curl -X POST http://localhost:8000/retry \
  -H "Content-Type: application/json" \
  -d '{"job_id": 123}'
```

## Production Deployment

### systemd Service

```bash
# Install service
sudo cp systemd/blog-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable blog-pipeline
sudo systemctl start blog-pipeline

# Check status
sudo systemctl status blog-pipeline
journalctl -u blog-pipeline -f
```

### Security

```bash
# Secure .env file
chmod 600 .env

# Run as dedicated user
sudo useradd -r -m -d /opt/blog-pipeline -s /bin/bash bot
sudo chown -R bot:bot /opt/blog-pipeline
```

## Development

### Run Tests

```bash
pytest tests/ --cov=app
```

### Linting

```bash
ruff check .
ruff format .
```

## Troubleshooting

### Jobs stuck in "queued"

```bash
# Restart service
sudo systemctl restart blog-pipeline

# Check logs
journalctl -u blog-pipeline -n 50
```

### WordPress upload fails

- Verify Application Password is active in WordPress
- Check `upload_max_filesize` in WordPress settings
- Test API manually:
  ```bash
  curl -u "user:pass" https://your-site.com/wp-json/wp/v2/posts
  ```

### "Permission denied" errors

```bash
sudo chown -R bot:bot /opt/blog-pipeline/var
chmod 600 /opt/blog-pipeline/.env
```

## Documentation

- **[MVP Specification](docs/SPEC_MVP.md)** - Detailed feature spec
- **[Operations Manual](docs/OPERATIONS.md)** - Setup and maintenance guide

## Roadmap

- [x] MVP: ZIP → WordPress draft automation
- [ ] P2: Theme-specific configurations (YAML profiles)
- [ ] P3: AI image generation (`{image: ...}` tags)
- [ ] P4: Auto-publish workflow + notifications
- [ ] P5: Git integration for version control
- [ ] P6: Prometheus metrics endpoint

## License

MIT

## Contributing

Pull requests welcome! Please ensure:
1. Tests pass: `pytest tests/`
2. Linting passes: `ruff check . && ruff format --check .`
3. Update documentation as needed

## Support

Issues: https://github.com/masahito-hub/Auto-blog/issues
