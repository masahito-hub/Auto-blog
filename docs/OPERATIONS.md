# Operations Manual

## Initial Setup

### Prerequisites
- Ubuntu 22.04+ (or Debian-based system)
- Python 3.11+
- WordPress site with Application Password enabled
- Slack workspace (optional, for notifications)

### Step 1: System User
```bash
# Create dedicated user
sudo useradd -r -m -d /opt/blog-pipeline -s /bin/bash bot
sudo passwd -l bot  # Lock password login
```

### Step 2: Clone and Install
```bash
sudo su - bot
cd /opt/blog-pipeline

# Clone repository (or copy files)
git clone https://github.com/masahito-hub/Auto-blog.git .

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Secrets
```bash
cp .env.example .env
nano .env
```

**Required Variables:**
```bash
WP_BASE_URL=https://your-wordpress-site.com
WP_USER=your_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx  # Generate from WP admin
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
IMAGES_PROVIDER=none
```

**Secure the file:**
```bash
chmod 600 .env
```

### Step 4: WordPress Application Password
1. Log into WordPress admin
2. Go to **Users → Profile**
3. Scroll to **Application Passwords**
4. Enter name: "Blog Pipeline"
5. Click **Add New Application Password**
6. Copy the generated password (format: `xxxx xxxx xxxx xxxx`)
7. Paste into `.env` as `WP_APP_PASSWORD`

**Required Permissions:**
- Create/edit posts
- Upload media files

### Step 5: Slack Webhook (Optional)
1. Go to https://api.slack.com/apps
2. Create new app → "From scratch"
3. Enable **Incoming Webhooks**
4. Add webhook to workspace
5. Copy webhook URL to `.env`

### Step 6: Install systemd Service
```bash
# Copy service file
sudo cp systemd/blog-pipeline.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable blog-pipeline

# Start service
sudo systemctl start blog-pipeline

# Check status
sudo systemctl status blog-pipeline
```

## Daily Operations

### Publishing a Post
1. Create ZIP file with structure:
   ```
   my-post.zip
   ├── post.md
   └── images/
       └── hero.jpg
   ```
2. Copy to server:
   ```bash
   scp my-post.zip user@server:/opt/blog-pipeline/var/inbox/
   ```
3. Monitor processing:
   ```bash
   curl http://localhost:8000/status | jq
   ```
4. Check WordPress drafts

### Monitoring Jobs
```bash
# Health check
curl http://localhost:8000/health

# Recent jobs
curl http://localhost:8000/status?limit=20

# Watch logs
journalctl -u blog-pipeline -f
```

### Retry Failed Job
```bash
# Get failed job ID from /status
curl -X POST http://localhost:8000/retry \
  -H "Content-Type: application/json" \
  -d '{"job_id": 123}'
```

## Troubleshooting

### Service Won't Start
```bash
# Check service logs
sudo journalctl -u blog-pipeline -n 50

# Check Python errors
sudo -u bot /opt/blog-pipeline/venv/bin/python -m app.server
```

### "Permission Denied" Errors
```bash
# Fix directory ownership
sudo chown -R bot:bot /opt/blog-pipeline/var

# Fix .env permissions
sudo chmod 600 /opt/blog-pipeline/.env
```

### WordPress Upload Fails
- Check `upload_max_filesize` in WordPress (Settings → Media)
- Verify Application Password is active
- Test WordPress API manually:
  ```bash
  curl -u "user:xxxx xxxx xxxx xxxx" \
    https://your-site.com/wp-json/wp/v2/posts
  ```

### Jobs Stuck in "queued"
```bash
# Check processor thread is running
sudo systemctl status blog-pipeline

# Restart service
sudo systemctl restart blog-pipeline
```

### Disk Space Issues
```bash
# Check disk usage
du -sh /opt/blog-pipeline/var/*

# Clean old work files (published jobs)
rm -rf /opt/blog-pipeline/var/work/*
```

## Maintenance

### Log Rotation
Create `/etc/logrotate.d/blog-pipeline`:
```
/var/log/blog-pipeline/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 bot bot
}
```

### Database Cleanup
```bash
# Clean jobs older than 30 days
sqlite3 /opt/blog-pipeline/var/queue.db \
  "DELETE FROM jobs WHERE updated_at < datetime('now', '-30 days')"
```

### Backup
```bash
# Backup database and published files
tar -czf backup-$(date +%Y%m%d).tar.gz \
  /opt/blog-pipeline/var/queue.db \
  /opt/blog-pipeline/var/published/
```

### Updates
```bash
sudo su - bot
cd /opt/blog-pipeline

# Pull latest code
git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
exit
sudo systemctl restart blog-pipeline
```

## Security Checklist
- [ ] `.env` file is mode 600
- [ ] Service runs as non-root user (`bot`)
- [ ] WordPress Application Password uses minimal permissions
- [ ] Slack webhook URL not exposed in logs
- [ ] Firewall blocks external access to port 8000 (use SSH tunnel or VPN)
- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`

## Performance Tuning

### Concurrent Processing
Edit `app/server.py` to add multiple processor threads:
```python
# Start N processor threads
for i in range(3):  # 3 concurrent jobs
    t = threading.Thread(target=process_jobs, daemon=True)
    t.start()
```

### Rate Limiting
If WordPress API returns 429 errors, increase retry delays in `.env`:
```bash
MAX_RETRIES=5
RETRY_DELAYS=60,300,900,3600,21600  # 1m, 5m, 15m, 1h, 6h
```

## Support
- GitHub Issues: https://github.com/masahito-hub/Auto-blog/issues
- Documentation: `/opt/blog-pipeline/docs/`
