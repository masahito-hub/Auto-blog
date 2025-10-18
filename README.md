# Blog Pipeline 🚀

**Automated WordPress publishing from ZIP archives**

Drop a ZIP file containing Markdown + images, and get a WordPress draft post automatically—no manual copy-pasting required.

[![Code Quality](https://github.com/masahito-hub/Auto-blog/actions/workflows/lint.yml/badge.svg)](https://github.com/masahito-hub/Auto-blog/actions/workflows/lint.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ⚡ Quick Start

```bash
# Clone and setup
git clone https://github.com/masahito-hub/Auto-blog.git
cd Auto-blog
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Add your WordPress credentials

# Validate setup
python scripts/check_config.py

# Run
python -m app.server
```

**Then drop a ZIP in `var/inbox/` and watch it publish!**

---

## ✨ Features

### Currently Implemented (v0.1.0 - MVP Phase 1)

✅ **Configuration System**
- Pydantic-based validation
- WordPress Application Password support
- Environment variable management
- Setup validation script

✅ **File Monitoring**
- Real-time ZIP file detection (watchdog)
- File stability checks (prevents processing incomplete uploads)
- ZIP integrity validation
- Automatic invalid file isolation

✅ **Job Queue**
- SQLite-based persistent queue
- State tracking (queued → running → done/failed)
- Exponential backoff retry (1m → 5m → 15m → 1h → 6h)
- Automatic stuck job recovery

✅ **Documentation**
- Complete setup guide with troubleshooting
- Architecture documentation
- Operations manual for production
- API reference

### Coming Soon (MVP Phase 2)

🔄 **Content Processing** (In Progress)
- ZIP extraction and parsing
- YAML frontmatter validation
- Markdown → HTML conversion
- Image file discovery

🔄 **WordPress Integration** (In Progress)
- REST API client
- Image upload to media library
- Draft post creation
- Featured image association

🔄 **Monitoring & Notifications**
- FastAPI health/status endpoints
- Slack success/failure notifications
- Job statistics and history

---

## 📋 MVP Roadmap

**Sprint 1 Progress:** 50% Complete (4/9 tasks)

- [x] [#1] Specification definition
- [x] [#2] Repository initialization & CI
- [x] [#3] Configuration & secrets management
- [x] [#4] Watcher & queue implementation
- [ ] [#5] **Processor implementation** ← Next
- [ ] [#6] Publisher (WordPress API)
- [ ] [#7] Server integration & threading
- [ ] [#8] Notifications & monitoring
- [ ] [#9] E2E testing & acceptance

**See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for detailed progress.**

---

## 🏗️ Architecture

```
var/inbox/*.zip → Watcher → Queue (SQLite)
                              ↓
                         Processor (extract + parse)
                              ↓
                         Publisher (WordPress API)
                              ↓
                    var/published/ + Slack notification
```

**Key Components:**
- **Watcher:** Monitors inbox for new ZIP files
- **Queue:** Persistent job storage with retry logic
- **Processor:** Extracts ZIP, parses frontmatter, converts Markdown
- **Publisher:** Uploads images and creates WordPress drafts
- **Server:** FastAPI monitoring endpoints

**See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for deep dive.**

---

## 📦 Input Format

### ZIP Structure

```
my-post.zip
├── post.md              # YAML frontmatter + Markdown content
└── images/              # Optional
    ├── hero.jpg         # Referenced in frontmatter
    └── diagram.png      # Referenced in content
```

### Example `post.md`

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

**Required fields:** `title`, `slug`  
**Optional fields:** `description`, `status`, `categories`, `tags`, `featured_image`, `author`, `date`

---

## 🔧 Configuration

### Required Environment Variables

```bash
# WordPress (Required)
WP_BASE_URL=https://your-wordpress-site.com
WP_USER=your_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx  # From WP Admin → Profile → Application Passwords

# Slack (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

**See [docs/SETUP.md](docs/SETUP.md) for complete setup guide.**

### Validation

```bash
# Check if everything is configured correctly
python scripts/check_config.py

# Expected output:
# ✅ Configuration loaded successfully
# ✅ WordPress URL is valid
# ✅ WordPress REST API is accessible
# ✅ WordPress authentication successful
# ✅ Can create posts (permissions OK)
# ✅ Can upload media (permissions OK)
# 🎉 All checks passed!
```

---

## 🚀 Usage

### Development Mode

```bash
# Start server
python -m app.server

# In another terminal, drop a ZIP
cp sample.zip var/inbox/

# Watch logs
tail -f logs/pipeline.log
```

### Production Deployment

```bash
# Install as systemd service
sudo cp systemd/blog-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable blog-pipeline
sudo systemctl start blog-pipeline

# Monitor
sudo systemctl status blog-pipeline
journalctl -u blog-pipeline -f
```

**See [docs/OPERATIONS.md](docs/OPERATIONS.md) for production guide.**

---

## 📊 API Endpoints

### `GET /health`
Health check

```json
{"ok": true, "version": "0.1.0"}
```

### `GET /status?limit=50`
Recent jobs + statistics

```json
{
  "jobs": [
    {
      "id": 1,
      "file": "my-post.zip",
      "slug": "keto-start-guide",
      "state": "done",
      "attempts": 1,
      "updated_at": "2025-10-06T10:30:00"
    }
  ],
  "stats": {"queued": 0, "running": 1, "done": 45, "failed": 2}
}
```

### `POST /retry`
Manually retry a failed job

```bash
curl -X POST http://localhost:8000/retry \
  -H "Content-Type: application/json" \
  -d '{"job_id": 123}'
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing

# Specific module
pytest tests/test_queue.py -v

# Linting
ruff check .
ruff format .
```

---

## 📖 Documentation

- **[SETUP.md](docs/SETUP.md)** - Installation and configuration guide
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and data flow
- **[SPEC_MVP.md](docs/SPEC_MVP.md)** - Complete MVP specification
- **[OPERATIONS.md](docs/OPERATIONS.md)** - Production deployment and monitoring
- **[PROJECT_STATUS.md](docs/PROJECT_STATUS.md)** - Current progress and roadmap
- **[HANDOFF.md](docs/HANDOFF.md)** - Handoff document for continuation

---

## 🛣️ Roadmap

### MVP (Current Sprint)
- [x] Configuration system
- [x] File monitoring
- [x] Job queue with retry logic
- [ ] Content processor (Markdown → HTML)
- [ ] WordPress publisher
- [ ] Monitoring API
- [ ] Slack notifications
- [ ] E2E testing

### Post-MVP (Future)
- [ ] **P2:** Theme-specific YAML configurations
- [ ] **P3:** AI image generation (`{image: ...}` tags)
- [ ] **P4:** Auto-publish workflow (draft → publish)
- [ ] **P5:** Git integration + Prometheus metrics
- [ ] **P6:** Multi-site support

---

## 🤝 Contributing

Pull requests welcome! Please ensure:

1. ✅ Tests pass: `pytest tests/`
2. ✅ Linting passes: `ruff check . && ruff format --check .`
3. ✅ Documentation updated
4. ✅ Follows existing code style

**See [docs/HANDOFF.md](docs/HANDOFF.md) for implementation guidance.**

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🆘 Support

- **Issues:** https://github.com/masahito-hub/Auto-blog/issues
- **Documentation:** [docs/](docs/)
- **Setup Help:** See [docs/SETUP.md](docs/SETUP.md) troubleshooting section

---

## 🎯 Project Context

**Goal:** Accelerate affiliate content production for 3 themes (Keto, Sleep, Infidelity Investigation)  
**Target:** 90 posts (30 each) for revenue validation  
**Approach:** Automate the bottleneck (WordPress entry) to focus on content quality  

**Built by:** ChatGPT (Lead) + Claude (Requirements + Implementation)

---

**Status:** 🚧 MVP in Progress (50% Complete) | **Next:** Processor Implementation
