# Test Fixtures

This directory contains sample files for testing.

## Files

### `sample-post.zip`

A minimal valid blog post ZIP for testing:

- Contains `post.md` with valid frontmatter
- Minimal content for fast testing
- Used in unit tests

### Creating Custom Test ZIPs

Use the helper function in tests:

```python
from tests.e2e.test_complete_workflow import create_sample_zip

zip_path = create_sample_zip(tmp_path)
```

Or create manually:

```bash
mkdir test-post
cd test-post

cat > post.md << 'EOF'
---
title: "My Test Post"
slug: "my-test-post"
description: "A test"
---

# Content

Your content here.
EOF

mkdir images
cp your-image.jpg images/

zip -r ../test-post.zip .
```

## Usage in Tests

```python
import zipfile
from pathlib import Path

def test_something():
    zip_path = Path("tests/fixtures/sample-post.zip")
    # Use in test
```
