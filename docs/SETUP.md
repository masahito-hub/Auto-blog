# Setup Guide

This guide walks you through setting up Blog Pipeline from scratch.

## Prerequisites

- **Python 3.11+** installed
- **WordPress site** with admin access
- **(Optional)** Slack workspace for notifications
- **VPS or local machine** for running the pipeline

---

## Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/masahito-hub/Auto-blog.git
cd Auto-blog

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 2: WordPress Application Password

**⚠️ Important:** Do NOT use your regular WordPress login password! You must create an Application Password.

### What is an Application Password?

Application Passwords are special passwords for WordPress REST API access. They are:
- Separate from your login password
- Can be revoked individually
- Cannot be used to log into WordPress admin
- More secure for API integrations

### How to Generate

1. **Log into WordPress Admin**
   - Go to your WordPress site and log in

2. **Navigate to Your Profile**
   - Click your username in the top-right corner
   - Select **"Edit Profile"** or **"Your Profile"**
   - Or go directly to: `https://your-site.com/wp-admin/profile.php`

3. **Scroll to Application Passwords Section**
   - Look for **"Application Passwords"** (usually near the bottom)
   - If you don't see this section, check:
     - WordPress version is 5.6+ (required)
     - Your site uses HTTPS (required for security)
     - Your user has Editor or Administrator role

4. **Create New Application Password**
   - In the **"New Application Password Name"** field, enter: `Blog Pipeline`
   - Click **"Add New Application Password"**
   - WordPress will generate a password like: `xxxx xxxx xxxx xxxx`

5. **Copy the Password**
   - ⚠️ **Copy it immediately!** You can't view it again after closing
   - The password has spaces, which is normal
   - Example format: `AbC1 2dEf 3GhI 4jKl mNoP 5qRs`

### Troubleshooting Application Passwords

**Problem:** "Application Passwords" section not visible

**Solutions:**
- **Check WordPress version**: Must be 5.6 or higher
  ```bash
  # Check version in WordPress Admin → Dashboard
  # Or via WP-CLI:
  wp core version
  ```

- **Enable HTTPS**: Application Passwords require SSL
  - Check your site URL starts with `https://`
  - Install SSL certificate (Let's Encrypt is free)
  - Many hosting providers offer one-click SSL

- **Check User Role**: Must be Editor or Administrator
  - Go to Users → All Users → Click your username
  - Verify "Role" field

- **Plugin Conflict**: Try disabling security plugins temporarily
  - Some security plugins block Application Passwords
  - Check plugin settings for "REST API" or "Application Password" options

**Problem:** REST API is disabled

```bash
# Test if REST API is accessible
curl -I https://your-site.com/wp-json/

# Should return: HTTP/2 200
# If 404 or 403, REST API is disabled
```

**Solution:** Enable REST API
- Check `.htaccess` for rules blocking `/wp-json/`
- Disable plugins that restrict REST API
- Add to `wp-config.php` if needed:
  ```php
  // Enable REST API
  add_filter('rest_authentication_errors', function($result) {
      if (!empty($result)) {
          return $result;
      }
      return true;
  });
  ```

---

## Step 3: Configure Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit with your favorite editor
nano .env
# Or: vim .env
# Or: code .env  (VS Code)
```

### Required Variables

Fill in these three required fields:

```bash
# Your WordPress site URL (no trailing slash)
WP_BASE_URL=https://myblog.com

# Your WordPress username
WP_USER=admin

# The Application Password you just created (copy/paste exactly)
WP_APP_PASSWORD=AbC1 2dEf 3GhI 4jKl mNoP 5qRs
```

### Optional: Slack Notifications

If you want Slack notifications:

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name it "Blog Pipeline" and select your workspace
4. Click **"Incoming Webhooks"** in the sidebar
5. Toggle **"Activate Incoming Webhooks"** to ON
6. Click **"Add New Webhook to Workspace"**
7. Select a channel (e.g., `#blog-notifications`)
8. Copy the webhook URL

Add to `.env`:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
```

### Secure Your .env File

```bash
# Set restrictive permissions (owner read/write only)
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- (600)
```

---

## Step 4: Validate Configuration

Run the configuration check script:

```bash
python scripts/check_config.py
```

**Expected output:**
```
✅ Configuration loaded successfully
✅ WordPress URL is valid: https://myblog.com
✅ WordPress REST API is accessible
✅ WordPress authentication successful
✅ Can create posts (permissions OK)
✅ Can upload media (permissions OK)
✅ All directories are writable
✅ Slack webhook is configured (optional)

🎉 All checks passed! Your environment is ready.
```

**If you see errors:**
- Read the error message carefully
- Check the troubleshooting section in this guide
- Verify your WordPress Application Password
- Ensure WordPress REST API is enabled

---

## Step 5: Test Run

### Create a Test Post

```bash
# Create a sample ZIP file
mkdir -p test-post/images
cat > test-post/post.md << 'EOF'
---
title: "Test Post from Blog Pipeline"
slug: "test-post-001"
description: "This is a test post to verify the pipeline works"
status: "draft"
---

# Welcome

This is a **test post** created by Blog Pipeline.

If you can see this in WordPress, everything is working! 🎉
EOF

# Create ZIP
cd test-post
zip -r ../test-post.zip .
cd ..
```

### Run the Pipeline

```bash
# Start the server
python -m app.server

# In another terminal, drop the ZIP
cp test-post.zip var/inbox/

# Watch the logs
# You should see:
# - File detected
# - Job enqueued
# - Processing started
# - Post created
# - Job completed
```

### Verify in WordPress

1. Log into WordPress Admin
2. Go to **Posts → All Posts**
3. Look for **"Test Post from Blog Pipeline"** in **Draft** status
4. Open it to verify content is correct

**Success!** 🎉 Your pipeline is working.

---

## Step 6: Production Deployment (Optional)

For production use on a VPS:

```bash
# Create dedicated user
sudo useradd -r -m -d /opt/blog-pipeline -s /bin/bash bot

# Copy files
sudo cp -r ~/Auto-blog/* /opt/blog-pipeline/
sudo chown -R bot:bot /opt/blog-pipeline

# Setup as service
sudo cp /opt/blog-pipeline/systemd/blog-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable blog-pipeline
sudo systemctl start blog-pipeline

# Check status
sudo systemctl status blog-pipeline
journalctl -u blog-pipeline -f
```

See [OPERATIONS.md](OPERATIONS.md) for detailed production setup.

---

## Common Issues

### "WordPress Application Password should be 24 characters"

**Problem:** Password validation fails

**Solution:**
- Ensure you copied the entire password (24 characters)
- Spaces are optional but include them if copying from WordPress
- Don't add extra characters or line breaks

### "REST API is not accessible"

**Problem:** Cannot connect to WordPress

**Solutions:**
1. Test manually:
   ```bash
   curl -I https://your-site.com/wp-json/
   ```
2. Should return `HTTP/2 200` or `HTTP/1.1 200`
3. If 404: REST API is disabled
4. If SSL error: Check HTTPS certificate

### "Authentication failed"

**Problem:** Wrong credentials

**Solutions:**
- Double-check `WP_USER` matches your WordPress username (not email)
- Regenerate Application Password if unsure
- Verify user has Editor or Administrator role
- Test with curl:
  ```bash
  curl -u "username:xxxx xxxx xxxx xxxx" \
    https://your-site.com/wp-json/wp/v2/posts
  ```

### "Permission denied" on directories

**Problem:** Cannot write to `var/` directories

**Solution:**
```bash
chmod -R 755 var/
# Or if running as specific user:
sudo chown -R your-user:your-group var/
```

---

## Next Steps

✅ Configuration complete!  
✅ Test post created successfully

Now you can:
1. Create real posts in ZIP format
2. Drop them in `var/inbox/`
3. Monitor via `/status` endpoint
4. Check WordPress for drafts

See [README.md](../README.md) for usage examples and [SPEC_MVP.md](SPEC_MVP.md) for detailed features.
