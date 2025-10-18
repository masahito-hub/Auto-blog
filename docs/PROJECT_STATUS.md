# Project Status - Blog Pipeline MVP

**Last Updated:** 2025-10-18  
**Phase:** Implementation (Sprint 1)  
**Overall Progress:** 50% (4/9 tasks complete)

---

## Sprint Overview

**Goal:** Build MVP for "ZIP → WordPress Draft" automation  
**Timeline:** 2025-10-06 to 2025-10-10  
**Status:** On Track ✅

---

## Task Completion Status

### ✅ Completed Tasks

#### [#1] Specification Definition
- ✅ Created `docs/SPEC_MVP.md` with detailed MVP scope
- ✅ Defined input format (ZIP structure, frontmatter)
- ✅ Documented API endpoints and acceptance criteria
- **Artifacts:** `SPEC_MVP.md`

#### [#2] Repository Initialization & CI
- ✅ Project structure created (app/, var/, docs/, tests/, systemd/)
- ✅ GitHub Actions workflow for ruff linting
- ✅ pyproject.toml with dependencies and tool configuration
- ✅ .gitignore and .env.example setup
- **Artifacts:** Full project skeleton, CI pipeline

#### [#3] Configuration & Secrets Management
- ✅ Enhanced `app/config.py` with Pydantic validation
- ✅ WordPress URL and Application Password validation
- ✅ Detailed `.env.example` with inline comments
- ✅ Created `docs/SETUP.md` with Application Password guide
- ✅ Implemented `scripts/check_config.py` validation script
- **Artifacts:** Validated configuration system, setup documentation

#### [#4] Watcher & Queue Implementation
- ✅ SQLite-based persistent job queue
- ✅ State machine: queued → running → done/failed
- ✅ Exponential backoff retry logic (1m → 6h)
- ✅ File watcher with stability checks (5s timeout)
- ✅ ZIP validation (integrity, post.md requirement)
- ✅ Invalid file isolation (var/failed/)
- ✅ Comprehensive test suite (test_queue.py, test_watcher.py)
- ✅ Created `docs/ARCHITECTURE.md`
- **Artifacts:** Fully functional queue and watcher modules with tests

---

### 🔄 In Progress

None - ready to start [#5]

---

### 📋 Remaining Tasks

#### [#5] Processor Implementation
**Status:** Not Started  
**Priority:** High (next task)  
**Dependencies:** [#4] complete

**Scope:**
- ZIP extraction to var/work/
- YAML frontmatter parsing
- Required field validation (title, slug)
- Markdown → HTML conversion
- Image file discovery
- Error handling for malformed input

**Deliverables:**
- Enhanced `app/processor.py`
- Test suite: `tests/test_processor.py`
- Sample ZIP files for testing

**Estimated Complexity:** Medium

---

#### [#6] Publisher Implementation
**Status:** Not Started  
**Priority:** High  
**Dependencies:** [#5] complete

**Scope:**
- WordPress REST API client
- Image upload to /wp/v2/media
- Draft post creation at /wp/v2/posts
- Featured image association
- Error handling (timeouts, 429, 5xx)
- Retry logic integration

**Deliverables:**
- Enhanced `app/publisher.py`
- Test suite: `tests/test_publisher.py` (with mocking)
- WordPress API integration tests

**Estimated Complexity:** Medium-High

---

#### [#7] API & Service Integration
**Status:** Not Started  
**Priority:** High  
**Dependencies:** [#6] complete

**Scope:**
- Integrate watcher, processor, publisher in server.py
- Background thread orchestration
- FastAPI endpoint finalization
- systemd service testing
- Logging and monitoring

**Deliverables:**
- Enhanced `app/server.py`
- Verified systemd service
- Health check validation

**Estimated Complexity:** Medium

---

#### [#8] Notifications & Retry Enhancement
**Status:** Not Started  
**Priority:** Medium  
**Dependencies:** [#7] complete

**Scope:**
- Slack webhook integration
- Success/failure notification formatting
- Retry notification with attempt count
- Error summary in notifications

**Deliverables:**
- Enhanced `app/utils.py`
- Notification templates
- Slack integration tests

**Estimated Complexity:** Low

---

#### [#9] E2E Testing & Acceptance
**Status:** Not Started  
**Priority:** High  
**Dependencies:** [#8] complete

**Scope:**
- Create test ZIP files (valid, invalid, edge cases)
- End-to-end workflow testing
- Performance testing (30 files)
- Acceptance criteria validation
- Production deployment guide

**Deliverables:**
- `tests/e2e/` test suite
- Sample ZIP files
- Performance benchmarks
- `docs/ACCEPTANCE.md`
- Updated `OPERATIONS.md`

**Estimated Complexity:** Medium

---

## Technical Decisions

### Architecture
- **Queue:** SQLite (sufficient for MVP, <10k jobs)
- **Concurrency:** Single-threaded processor (MVP)
- **File Monitoring:** watchdog library
- **Markdown:** Python-markdown with extensions (extra, codehilite, toc)

### Key Design Choices

1. **File Stability Check (5 seconds)**
   - Prevents processing incomplete uploads
   - Configurable via `ZipFileHandler.stability_timeout`

2. **Exponential Backoff Retry**
   - Delays: 1m, 5m, 15m, 1h, 6h
   - Max attempts: 5 (configurable)
   - Rationale: Quick recovery from transient errors, longer waits for persistent issues

3. **Invalid File Handling**
   - Move to `var/failed/` instead of deleting
   - Allows manual inspection and recovery

4. **State Machine**
   - Simple 4-state model: queued, running, done, failed
   - Clear transition rules
   - Idempotent state updates

5. **WordPress Authentication**
   - Application Password (not admin password)
   - HTTP Basic Auth over HTTPS
   - More secure than admin credentials

---

## Known Issues & Limitations

### MVP Limitations (By Design)
1. ❌ No AI image generation (`{image: ...}` tags pass through)
2. ❌ Categories/tags must exist in WordPress (no auto-create)
3. ❌ Single-threaded processing (1 job at a time)
4. ❌ Draft status only (no auto-publish)
5. ❌ No theme-specific configuration (YAML profiles)

### Technical Debt
1. **TODO:** Add category/tag ID lookup and creation
2. **TODO:** Implement `{image: ...}` tag replacement (P3)
3. **TODO:** Add concurrent processing option (P2)
4. **TODO:** Prometheus metrics endpoint (P5)

### Open Questions
1. Should we retry on WordPress 429 (rate limit) immediately or follow backoff?
   - **Decision Needed:** Current implementation follows backoff
2. What to do with duplicate slugs?
   - **Decision Needed:** WordPress auto-appends `-2`, `-3`, etc.

---

## Blockers & Risks

### Current Blockers
- ❌ None

### Potential Risks
1. **WordPress Application Password Confusion**
   - Mitigation: Detailed setup guide with troubleshooting
   - Status: Addressed in `docs/SETUP.md`

2. **Large File Uploads**
   - Risk: WordPress upload_max_filesize limit
   - Mitigation: Pre-validation in watcher (100MB limit), error handling
   - Status: Implemented

3. **Queue Growth**
   - Risk: SQLite performance degradation with >10k jobs
   - Mitigation: Cleanup job (30-day retention)
   - Status: Implemented (`cleanup_old_jobs()`)

---

## Metrics & Success Criteria

### MVP Acceptance Criteria
- ✅ Configuration validation script works
- ⏳ Sample ZIP creates WordPress draft within 60 seconds
- ⏳ Title, slug, content, featured image correctly set
- ⏳ `/health` returns 200
- ⏳ `/status` shows job progression
- ⏳ Failed jobs trigger auto-retry
- ⏳ Successful jobs move ZIP to var/published/
- ⏳ Slack notifications work (if configured)

### Performance Targets
- **Processing Time:** <30 seconds per post (typical)
- **Throughput:** ~120 posts/hour (with current serial processing)
- **Error Rate:** <5% in normal operation
- **Retry Success:** >80% of failures resolved within 3 retries

---

## Next Steps

### Immediate (Next Session)
1. Implement [#5] Processor
   - Focus: ZIP extraction, frontmatter parsing, Markdown conversion
   - Tests: Valid/invalid frontmatter, Markdown features

2. Implement [#6] Publisher
   - Focus: WordPress API integration, image upload
   - Tests: Mock WordPress API responses

### Short-term (This Sprint)
3. Complete [#7] Integration
4. Add [#8] Notifications
5. Run [#9] E2E tests
6. Document production deployment

### Post-MVP (Future Sprints)
- P2: Theme configuration (YAML profiles)
- P3: AI image generation
- P4: Auto-publish workflow
- P5: Git integration + metrics

---

## Resources

### Documentation
- `docs/SPEC_MVP.md` - Complete MVP specification
- `docs/SETUP.md` - Setup and configuration guide
- `docs/OPERATIONS.md` - Production operations manual
- `docs/ARCHITECTURE.md` - System architecture and design
- `README.md` - Project overview and quick start

### Code Structure
- `app/` - Main application modules
- `tests/` - Test suite (pytest)
- `scripts/` - Utility scripts (check_config.py)
- `systemd/` - Service configuration
- `var/` - Runtime directories (inbox, work, published, failed)

### External References
- WordPress REST API: https://developer.wordpress.org/rest-api/
- Application Passwords: https://make.wordpress.org/core/2020/11/05/application-passwords/
- watchdog docs: https://python-watchdog.readthedocs.io/

---

## Team Notes

### Communication Protocol
- **Project Lead:** ChatGPT (司令塔)
- **Requirements:** Claude (要件定義)
- **Implementation:** Claude Code
- **Review:** Claude Code Review

### Collaboration Tips for Next Session
1. Review this status document first
2. Check `docs/ARCHITECTURE.md` for design decisions
3. Run `scripts/check_config.py` to verify environment
4. Focus on one module at a time (Processor → Publisher)
5. Write tests alongside implementation

---

**End of Status Report**
