# Architecture Documentation

## System Overview

Blog Pipeline is a file-based automation system that monitors ZIP archives and publishes them to WordPress. The system follows an event-driven architecture with a persistent job queue.

```
┌─────────────┐
│   Inbox     │  ZIP files dropped here
│  Directory  │
└──────┬──────┘
       │
       │ File System Events
       ↓
┌──────────────┐
│   Watcher    │  Monitors for new/modified files
│  (watchdog)  │  Validates file stability
└──────┬───────┘
       │
       │ Enqueue
       ↓
┌──────────────┐
│     Queue    │  SQLite-based persistent queue
│   (SQLite)   │  Manages retry logic
└──────┬───────┘
       │
       │ Get Next Job
       ↓
┌──────────────┐
│  Processor   │  Extract ZIP, parse frontmatter
│              │  Convert Markdown → HTML
└──────┬───────┘
       │
       │ PostData
       ↓
┌──────────────┐
│  Publisher   │  Upload images to WordPress
│  (WP REST)   │  Create draft post
└──────┬───────┘
       │
       │ Success/Failure
       ↓
┌──────────────┐
│  Notifier    │  Send Slack notifications
│   (Slack)    │  Log results
└──────────────┘
```

## Core Components

### 1. Configuration (`app/config.py`)

**Responsibility:** Central configuration management

- Load settings from environment variables (`.env`)
- Validate required fields (WordPress URL, credentials)
- Provide default values for optional settings
- Initialize directory structure

**Key Features:**
- Pydantic-based validation
- Automatic path resolution
- Environment validation method

### 2. Watcher (`app/watcher.py`)

**Responsibility:** Monitor inbox directory for new ZIP files

- Uses `watchdog` library for file system events
- Tracks pending files with size/time tracking
- Implements stability check (5-second default)
- Validates ZIP integrity before enqueuing
- Moves invalid files to `var/failed/`

**State Machine:**
```
File Created → Pending → Stable → Validated → Enqueued
                 ↓         ↓         ↓
              Modified   Still     Invalid
                         Writing   → Failed
```

**Stability Logic:**
- File size unchanged for N seconds
- ZIP can be opened and tested
- Contains required `post.md` file

### 3. Queue (`app/queue.py`)

**Responsibility:** Persistent job queue with retry logic

- SQLite-based storage
- State machine: `queued → running → done/failed`
- Exponential backoff retry (1m → 5m → 15m → 1h → 6h)
- Max retry limit (default: 5 attempts)

**Database Schema:**
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    slug TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    next_retry_at TIMESTAMP
);
```

**Indices:**
- `(state, next_retry_at)` - Fast job retrieval
- `slug` - Lookup by post slug
- `created_at DESC` - Recent jobs

### 4. Processor (`app/processor.py`)

**Responsibility:** Extract and parse ZIP contents

- Extract ZIP to `var/work/<slug>/`
- Parse YAML frontmatter from `post.md`
- Validate required fields (`title`, `slug`)
- Convert Markdown to HTML
- Return structured `PostData` object

**Frontmatter Validation:**
- Required: `title`, `slug`
- Optional: `description`, `status`, `categories`, `tags`, `featured_image`, `author`, `date`

### 5. Publisher (`app/publisher.py`)

**Responsibility:** WordPress REST API integration

- Upload images to `/wp/v2/media`
- Create draft post at `/wp/v2/posts`
- Set featured image
- Handle API errors and timeouts

**Authentication:**
- HTTP Basic Auth with Application Password
- Format: `username:xxxx xxxx xxxx xxxx`

**API Flow:**
1. Upload featured image (if specified) → Get media ID
2. Upload inline images → Replace references
3. Create post with content + media ID
4. Return post URL

### 6. Server (`app/server.py`)

**Responsibility:** FastAPI web server for monitoring

**Endpoints:**
- `GET /health` - Health check (200 OK)
- `GET /status?limit=N` - Recent jobs + stats
- `POST /retry` - Manually retry failed job

**Background Threads:**
- Watcher thread (monitors inbox)
- Processor thread (processes queue)

### 7. Utils (`app/utils.py`)

**Responsibility:** Common utilities

- Slack webhook notifications
- Logging helpers
- Error formatting

## Data Flow

### Happy Path

```
1. User drops sample.zip in var/inbox/
2. Watcher detects file creation
3. Watcher waits 5s for file stability
4. Watcher validates ZIP integrity
5. Watcher enqueues job → Queue (state: queued)
6. Processor picks up job → Queue (state: running)
7. Processor extracts ZIP to var/work/sample/
8. Processor parses post.md frontmatter
9. Processor converts Markdown → HTML
10. Publisher uploads images to WordPress
11. Publisher creates draft post
12. Queue updates job → (state: done)
13. File moved to var/published/sample.zip
14. Slack notification: "✅ Draft created"
```

### Error Path

```
1. User drops invalid.zip
2. Processor fails: "Missing required field: title"
3. Queue updates job → (state: failed, attempts: 1)
4. Queue sets next_retry_at = now + 60s
5. After 60s, Queue makes job available
6. Processor retries...
7. After 5 failed attempts:
   - Queue sets state: failed (permanent)
   - Slack notification: "❌ Failed permanently"
   - File remains in var/inbox/ for manual review
```

## State Transitions

### Job State Machine

```
          ┌─────────┐
    ┌────→│ queued  │←────┐
    │     └────┬────┘     │
    │          │          │
    │          ↓          │
    │     ┌─────────┐     │
    │     │ running │     │
    │     └────┬────┘     │
    │          │          │
    │      Success/       │
    │       Failure       │
    │          │          │
    │     ┌────┴────┐     │
    │     ↓         ↓     │
┌───┴────┐      ┌────┴────┐
│  done  │      │ failed  │
└────────┘      └────┬────┘
                     │
              Max retries? No
                     │
                     └──────┘ (retry)
```

**State Rules:**
- `queued`: Initial state or after retry
- `running`: Currently being processed
- `done`: Successfully published
- `failed`: Error occurred, will retry if attempts < max_retries

**Transitions:**
- `queued → running`: Processor picks up job
- `running → done`: Successful WordPress publish
- `running → failed`: Error + retry scheduled
- `failed → queued`: Retry time reached

## Retry Strategy

**Exponential Backoff:**

| Attempt | Delay   | Total Elapsed |
|---------|---------|---------------|
| 1       | 1 min   | 1 min         |
| 2       | 5 min   | 6 min         |
| 3       | 15 min  | 21 min        |
| 4       | 1 hour  | 1h 21min      |
| 5       | 6 hours | 7h 21min      |

**Rationale:**
- Quick retries for transient errors (network blip)
- Longer delays for persistent issues (API rate limit)
- Manual intervention window before max retries

## Directory Structure

```
/opt/blog-pipeline/
├── .env                    # Secrets (600 permissions)
├── app/                    # Python modules
├── var/
│   ├── inbox/              # Drop ZIPs here
│   ├── work/               # Temporary extraction
│   │   └── sample-post/    # Extracted content
│   ├── published/          # Successfully processed
│   ├── failed/             # Invalid ZIPs
│   └── queue.db            # SQLite database
├── docs/                   # Documentation
├── tests/                  # Test suite
└── systemd/                # Service files
```

## Security Considerations

### Secrets Management
- `.env` file with 600 permissions
- No secrets in logs or error messages
- Application Password (not admin password)

### Input Validation
- ZIP size limit (100MB default)
- ZIP integrity check (testzip)
- Frontmatter validation
- Path traversal prevention (no `../` in ZIP)

### Process Isolation
- Dedicated system user (`bot`)
- No shell command execution
- Sandboxed work directory

### API Security
- HTTPS only for WordPress
- Basic Auth over TLS
- Timeout on all HTTP requests
- Rate limit respect (429 handling)

## Performance Characteristics

### Throughput
- **Serial processing**: 1 job at a time (MVP)
- **Typical job time**: 10-30 seconds
  - ZIP extraction: 1-2s
  - Markdown processing: <1s
  - Image upload: 5-15s (depends on count/size)
  - Post creation: 1-2s

### Scalability Limits
- **Queue size**: Unlimited (SQLite)
- **Concurrent jobs**: 1 (configurable to N threads)
- **Max file size**: 100MB (configurable)
- **Database**: Suitable for <10,000 jobs (consider PostgreSQL for larger scale)

### Resource Usage
- **Memory**: ~50-100MB baseline
- **Disk**: Proportional to `var/work/` content
- **CPU**: Minimal (I/O bound)

## Monitoring

### Health Checks
```bash
# Service alive?
curl http://localhost:8000/health

# Recent job status
curl http://localhost:8000/status | jq

# System logs
journalctl -u blog-pipeline -f
```

### Metrics to Watch
- Failed job rate (>10% = investigate)
- Average processing time (>60s = slow)
- Queue depth (>20 = backlog)
- Disk usage (`var/work/` growth)

## Future Enhancements

### P2: Theme Configuration
- YAML profiles per theme
- Category/tag auto-creation
- Slug prefix rules

### P3: Image Generation
- OpenAI DALL-E integration
- `{image: ...}` tag replacement
- Style presets per theme

### P4: Auto-Publish
- Draft → Publish workflow
- Schedule publishing
- Public URL notifications

### P5: Advanced Features
- Multi-tenancy (multiple WP sites)
- Prometheus metrics
- Git commit integration
- Webhook triggers
