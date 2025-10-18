# Handoff Document - Blog Pipeline MVP

**Context:** This document helps the next Claude (or team member) continue implementation seamlessly.

**Last Updated:** 2025-10-18  
**Current Phase:** Mid-implementation (50% complete)  
**Next Task:** [#5] Processor Implementation

---

## Quick Context

### What We're Building
An automated WordPress publishing pipeline that:
1. Monitors a directory for ZIP files
2. Extracts and parses Markdown posts with YAML frontmatter
3. Uploads images to WordPress
4. Creates draft posts automatically
5. Handles retries and notifications

**Business Goal:** Accelerate content production for 3 affiliate themes (Keto, Sleep, Infidelity Investigation) - need to publish 90 posts (30 each) quickly to validate revenue potential.

---

## What's Already Done ✅

### 1. Project Foundation
- ✅ Repository structure (`app/`, `var/`, `docs/`, `tests/`, `systemd/`)
- ✅ GitHub Actions CI with ruff linting
- ✅ Dependencies defined (`requirements.txt`, `pyproject.toml`)

### 2. Configuration System
- ✅ `app/config.py` - Pydantic-based settings with validation
- ✅ `.env.example` - Comprehensive template
- ✅ `scripts/check_config.py` - Environment validation script
- ✅ `docs/SETUP.md` - WordPress Application Password guide

**Key Files:**
- `.env` needs: `WP_BASE_URL`, `WP_USER`, `WP_APP_PASSWORD`, optionally `SLACK_WEBHOOK_URL`

### 3. Queue System (Complete)
- ✅ `app/queue.py` - SQLite-based job queue
- ✅ State machine: `queued → running → done/failed`
- ✅ Exponential backoff retry: 1m, 5m, 15m, 1h, 6h
- ✅ Job statistics and recent job queries
- ✅ Cleanup and stuck job recovery

**Key Functions:**
- `init_db()` - Create schema
- `enqueue_job(path)` - Add new job
- `get_next_job()` - Fetch job to process
- `update_job_state(id, state, ...)` - Update job
- `get_job_stats()` - Dashboard data

### 4. File Watcher (Complete)
- ✅ `app/watcher.py` - watchdog-based file monitoring
- ✅ File stability check (5-second timeout)
- ✅ ZIP validation (integrity + post.md requirement)
- ✅ Invalid file isolation to `var/failed/`
- ✅ 100MB file size limit

**How It Works:**
1. Detects `*.zip` files in `var/inbox/`
2. Waits for file size to stabilize (5s)
3. Validates ZIP integrity and structure
4. Enqueues valid files
5. Moves invalid files to `var/failed/`

### 5. Tests
- ✅ `tests/test_queue.py` - Full queue coverage
- ✅ `tests/test_processor.py` - Basic skeleton (needs expansion)
- ✅ `tests/test_watcher.py` - Watcher logic coverage

### 6. Documentation
- ✅ `docs/SPEC_MVP.md` - Complete MVP specification
- ✅ `docs/SETUP.md` - Setup and troubleshooting
- ✅ `docs/OPERATIONS.md` - Production deployment guide
- ✅ `docs/ARCHITECTURE.md` - System design and data flow
- ✅ `docs/PROJECT_STATUS.md` - Current progress tracking
- ✅ `README.md` - Project overview

---

## What's NOT Done Yet 🔲

### Critical Path (Must Complete for MVP)

#### [#5] Processor - **NEXT TASK**
**Module:** `app/processor.py` (skeleton exists, needs implementation)

**What Needs to Be Done:**
1. Enhance `extract_zip(path)` with cleanup logic
2. Implement robust frontmatter parsing:
   ```python
   # Required fields: title, slug
   # Optional: description, status, categories, tags, featured_image, author, date
   ```
3. Validate required fields and raise clear errors
4. Convert Markdown → HTML using `markdown` library
5. Handle edge cases:
   - Missing frontmatter
   - Invalid YAML
   - Nested directories in ZIP
   - Special characters in filenames

**Test Cases to Add:**
- Valid frontmatter + Markdown
- Missing required fields (title, slug)
- Invalid YAML syntax
- Markdown features (headers, bold, links, code blocks)
- Image references in content

**Skeleton Code Location:** `app/processor.py` (lines 40-100)

---

#### [#6] Publisher
**Module:** `app/publisher.py` (skeleton exists, needs implementation)

**What Needs to Be Done:**
1. Complete `WordPressPublisher` class:
   - Test connection to WordPress API
   - Handle authentication errors
2. Implement `upload_media(image_path)`:
   - POST to `/wp/v2/media`
   - Handle file types (jpg, png, webp, gif)
   - Return media ID
3. Implement `create_post(post_data, featured_media_id)`:
   - POST to `/wp/v2/posts`
   - Set title, slug, content, excerpt, featured_media
   - Return post URL
4. Error handling:
   - Network timeouts (30s default)
   - HTTP 429 (rate limit) → raise for retry
   - HTTP 5xx (server error) → raise for retry
   - HTTP 401/403 (auth) → fail permanently

**Test Strategy:**
- Mock WordPress API responses using `responses` library
- Test successful upload flow
- Test error scenarios (timeout, 429, 500, 401)

**Skeleton Code Location:** `app/publisher.py` (lines 20-80)

---

#### [#7] Integration
**Module:** `app/server.py` (skeleton exists, needs enhancement)

**What Needs to Be Done:**
1. Complete `process_jobs()` function:
   - Orchestrate: processor → publisher → queue update
   - Handle errors gracefully
   - Move files to `var/published/` on success
2. Start background threads:
   - Watcher thread
   - Processor thread
3. Ensure clean shutdown on SIGTERM
4. Add logging for observability

**Skeleton Code Location:** `app/server.py` (lines 80-150)

---

#### [#8] Notifications
**Module:** `app/utils.py` (skeleton exists)

**What Needs to Be Done:**
1. Implement `notify_slack(message, success)`:
   - Format message with emoji (✅/❌)
   - Include post URL on success
   - Include error summary on failure
   - Graceful failure if webhook unavailable
2. Add notification calls in `server.py`:
   - Success: `[{slug}] Draft created: <URL>`
   - Failure: `[{slug}] Failed (attempt {n}/{max}): <error>`

**Skeleton Code Location:** `app/utils.py` (lines 10-40)

---

#### [#9] E2E Testing
**New:** `tests/e2e/` directory

**What Needs to Be Done:**
1. Create sample ZIP files:
   - `tests/fixtures/sample-valid.zip`
   - `tests/fixtures/sample-no-frontmatter.zip`
   - `tests/fixtures/sample-missing-slug.zip`
   - `tests/fixtures/sample-with-images.zip`
2. Write end-to-end test:
   ```python
   def test_complete_workflow():
       # 1. Drop ZIP in inbox
       # 2. Wait for processing
       # 3. Verify WordPress draft created
       # 4. Verify file moved to published/
       # 5. Verify job state = done
   ```
3. Acceptance criteria validation
4. Performance benchmarks (30 files)

---

## Key Technical Details

### Input Format (ZIP Structure)
```
my-post.zip
├── post.md              # YAML frontmatter + Markdown content
└── images/              # Optional
    ├── hero.jpg         # Referenced in featured_image
    └── diagram.png      # Referenced in content
```

### Frontmatter Example
```yaml
---
title: "Post Title"              # Required
slug: "post-slug-001"            # Required
description: "Meta description"  # Optional
status: "draft"                  # Fixed to "draft" in MVP
categories: ["Category1"]        # Optional (must exist in WP)
tags: ["tag1", "tag2"]           # Optional (must exist in WP)
featured_image: "images/hero.jpg"  # Optional
author: "Author Name"            # Optional
date: "2025-10-05"               # Optional
---

# Your Markdown Content
Introduction paragraph...
```

### WordPress API Endpoints
- `POST /wp-json/wp/v2/media` - Upload images
- `POST /wp-json/wp/v2/posts` - Create posts
- Auth: HTTP Basic Auth with Application Password

### Directory Flow
```
var/inbox/         → Watcher detects ZIP
  ↓
var/work/          → Processor extracts ZIP
  ↓
WordPress          → Publisher uploads
  ↓
var/published/     → Success: Move ZIP here
  OR
var/inbox/         → Failure: Leave for retry
```

---

## Implementation Tips

### For Processor Implementation
1. **ZIP Extraction:**
   ```python
   # Use context manager
   with zipfile.ZipFile(path, 'r') as zip_ref:
       zip_ref.extractall(work_dir)
   
   # Prevent path traversal
   for name in zip_ref.namelist():
       if name.startswith('../') or name.startswith('/'):
           raise ProcessorError(f"Invalid path: {name}")
   ```

2. **Frontmatter Parsing:**
   ```python
   # Reliable split method
   if not content.startswith('---'):
       raise ProcessorError("Missing frontmatter")
   
   parts = content.split('---', 2)
   if len(parts) < 3:
       raise ProcessorError("Invalid frontmatter format")
   
   frontmatter = yaml.safe_load(parts[1])
   markdown_content = parts[2].strip()
   ```

3. **Markdown Conversion:**
   ```python
   import markdown
   
   html = markdown.markdown(
       content,
       extensions=['extra', 'codehilite', 'toc']
   )
   ```

### For Publisher Implementation
1. **Image Upload:**
   ```python
   with open(image_path, 'rb') as f:
       files = {'file': (image_path.name, f, 'image/jpeg')}
       headers = {'Content-Disposition': f'attachment; filename="{image_path.name}"'}
       
       response = requests.post(
           f"{base_url}/wp-json/wp/v2/media",
           auth=auth,
           files=files,
           headers=headers,
           timeout=30
       )
   
   media_id = response.json()['id']
   ```

2. **Post Creation:**
   ```python
   payload = {
       'title': post_data.title,
       'slug': post_data.slug,
       'content': post_data.get_html_content(),
       'excerpt': post_data.description,
       'status': 'draft',
       'featured_media': featured_media_id,
   }
   
   response = requests.post(
       f"{base_url}/wp-json/wp/v2/posts",
       auth=auth,
       json=payload,
       timeout=30
   )
   ```

3. **Error Handling Pattern:**
   ```python
   if response.status_code == 429:
       raise PublisherError("Rate limited - will retry")
   elif response.status_code >= 500:
       raise PublisherError(f"Server error: {response.status_code}")
   elif response.status_code == 401:
       raise PublisherError("Authentication failed - check credentials")
   elif response.status_code not in (200, 201):
       raise PublisherError(f"Unexpected response: {response.status_code}")
   ```

---

## Testing Strategy

### Unit Tests
- Test each module independently
- Mock external dependencies (WordPress API, file system)
- Use pytest fixtures for setup/teardown

### Integration Tests
- Test module interactions (processor → publisher)
- Use real SQLite database (temp directory)
- Mock only external APIs

### E2E Tests
- Full workflow with real files
- Can use test WordPress instance or mocked API
- Verify acceptance criteria

### Running Tests
```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/test_processor.py -v

# With coverage
pytest tests/ --cov=app --cov-report=term-missing
```

---

## Common Pitfalls to Avoid

1. **Don't forget to close resources:**
   - Use context managers for files and connections
   - Clean up extracted ZIPs in `var/work/`

2. **Handle encoding properly:**
   - Always specify `encoding='utf-8'` when reading text files
   - WordPress API expects UTF-8

3. **Validate early:**
   - Check required fields immediately in processor
   - Don't upload images if post will fail later

4. **Log liberally:**
   - Use logger.info for workflow steps
   - Use logger.error for failures with context
   - Never log secrets (Application Password)

5. **Make operations idempotent where possible:**
   - Re-processing same ZIP should be safe
   - WordPress handles duplicate slugs automatically

---

## Quick Start for Next Session

```bash
# 1. Pull latest code
git pull origin main

# 2. Review status
cat docs/PROJECT_STATUS.md
cat docs/ARCHITECTURE.md

# 3. Check what's left
grep -r "TODO" app/
grep -r "pass" app/

# 4. Run existing tests
pytest tests/ -v

# 5. Start implementing [#5] Processor
# Focus: app/processor.py lines 40-100
# Add tests: tests/test_processor.py

# 6. Test incrementally
pytest tests/test_processor.py -v -k "frontmatter"
```

---

## Questions for Consideration

1. **Should we support nested directories in ZIPs?**
   - Current spec: Flat structure preferred
   - Recommendation: Support but flatten during extraction

2. **What if WordPress returns 429 (rate limit)?**
   - Current: Follows normal retry backoff
   - Alternative: Immediate retry after short delay?

3. **Should we validate image file types before upload?**
   - Current: Yes, in `image_gen.py` validator
   - Allowed: jpg, jpeg, png, webp, gif

4. **What to do with existing running jobs on startup?**
   - Current: `reset_stuck_jobs()` resets jobs older than 1 hour
   - Alternative: Resume or fail them?

---

## Success Metrics Reminder

**MVP is successful when:**
- ✅ Configuration validation passes
- ⏳ Sample ZIP → WordPress draft in <60s
- ⏳ All post fields correctly populated
- ⏳ `/health` and `/status` endpoints work
- ⏳ Failed jobs auto-retry successfully
- ⏳ Successful jobs move to `var/published/`
- ⏳ Slack notifications work

**Current Status:** 4/8 criteria met (infrastructure ready, business logic pending)

---

## Contact / Questions

If you're picking this up and have questions:
1. Review `docs/ARCHITECTURE.md` for design rationale
2. Check `docs/SETUP.md` for environment setup
3. See `docs/SPEC_MVP.md` for complete requirements
4. Refer to this document for implementation guidance

**Happy coding!** 🚀

---

**End of Handoff Document**
