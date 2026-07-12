"""File watcher for monitoring ZIP files in inbox directory."""

import logging
import time
import zipfile
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import settings
from app.queue import enqueue_job

logger = logging.getLogger(__name__)


class ZipFileHandler(FileSystemEventHandler):
    """Handler for ZIP file creation events."""

    def __init__(self):
        super().__init__()
        # Track pending files with their detection time and size
        self.pending_files: dict[str, dict] = {}
        self.stability_timeout = 5  # seconds
        self.max_file_size = 100 * 1024 * 1024  # 100MB

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() != ".zip":
            return

        logger.info(f"Detected new ZIP file: {path.name}")

        # Initial validation
        if not self._validate_file_basic(path):
            return

        self.pending_files[str(path)] = {
            "detected_at": time.time(),
            "last_size": path.stat().st_size if path.exists() else 0,
            "checked_count": 0,
        }

    def on_modified(self, event):
        """Handle file modification event (file still being written)."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() != ".zip":
            return

        file_path = str(path)
        if file_path in self.pending_files:
            # Update last known size
            if path.exists():
                self.pending_files[file_path]["last_size"] = path.stat().st_size
                self.pending_files[file_path]["detected_at"] = time.time()
                logger.debug(f"File still being written: {path.name}")

    def _validate_file_basic(self, path: Path) -> bool:
        """Basic file validation.

        Args:
            path: Path to ZIP file

        Returns:
            True if file passes basic validation
        """
        if not path.exists():
            logger.warning(f"File disappeared: {path.name}")
            return False

        # Check file size
        file_size = path.stat().st_size
        if file_size == 0:
            logger.warning(f"Empty file: {path.name}")
            return False

        if file_size > self.max_file_size:
            logger.error(
                f"File too large: {path.name} ({file_size / 1024 / 1024:.1f}MB > {self.max_file_size / 1024 / 1024:.0f}MB)"
            )
            return False

        return True

    def _validate_file_complete(self, path: Path) -> bool:
        """Validate that file is a valid ZIP and completely written.

        Args:
            path: Path to ZIP file

        Returns:
            True if file is a valid, complete ZIP
        """
        try:
            # Try to open and read ZIP structure
            with zipfile.ZipFile(path, "r") as zip_ref:
                # Test ZIP integrity
                bad_file = zip_ref.testzip()
                if bad_file:
                    logger.error(f"Corrupt ZIP file {path.name}: bad file {bad_file}")
                    return False

                # Check for required post.md
                file_list = zip_ref.namelist()
                has_post_md = any(f.endswith("post.md") or f == "post.md" for f in file_list)

                if not has_post_md:
                    logger.error(f"ZIP {path.name} missing post.md")
                    return False

                logger.debug(f"ZIP validated: {path.name} ({len(file_list)} files)")
                return True

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file {path.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error validating {path.name}: {e}")
            return False

    def _is_file_stable(self, path: Path, info: dict) -> bool:
        """Check if file is stable (no longer being written).

        Args:
            path: Path to file
            info: File tracking info

        Returns:
            True if file size hasn't changed for stability_timeout seconds
        """
        if not path.exists():
            return False

        current_time = time.time()
        current_size = path.stat().st_size
        time_since_detection = current_time - info["detected_at"]

        # Check if size has changed
        if current_size != info["last_size"]:
            info["last_size"] = current_size
            info["detected_at"] = current_time
            info["checked_count"] = 0
            return False

        # File size stable, wait for timeout
        info["checked_count"] += 1

        if time_since_detection >= self.stability_timeout:
            return True

        return False

    def check_stable_files(self):
        """Check if pending files are stable and enqueue them."""
        stable_files = []

        for file_path, info in list(self.pending_files.items()):
            path = Path(file_path)

            if not path.exists():
                logger.warning(f"Pending file disappeared: {path.name}")
                stable_files.append(file_path)
                continue

            if self._is_file_stable(path, info):
                logger.info(f"File stable, validating: {path.name}")

                # Validate ZIP is complete and valid
                if self._validate_file_complete(path):
                    try:
                        job_id = enqueue_job(path)
                        logger.info(
                            f"Enqueued job {job_id} for {path.name} "
                            f"({path.stat().st_size / 1024:.1f}KB)"
                        )
                        stable_files.append(file_path)
                    except Exception as e:
                        logger.error(f"Failed to enqueue {path.name}: {e}")
                        stable_files.append(file_path)
                else:
                    logger.error(f"Invalid ZIP file, skipping: {path.name}")
                    # Move to failed directory if it exists
                    failed_dir = settings.base_dir / "var" / "failed"
                    failed_dir.mkdir(exist_ok=True)
                    try:
                        failed_path = failed_dir / path.name
                        path.rename(failed_path)
                        logger.info(f"Moved invalid file to: {failed_path}")
                    except Exception as e:
                        logger.error(f"Failed to move invalid file: {e}")
                    stable_files.append(file_path)

        # Remove processed files from pending
        for file_path in stable_files:
            self.pending_files.pop(file_path, None)


def start_watcher():
    """Start the file watcher."""
    logger.info(f"Starting watcher on {settings.inbox_dir}")

    # Ensure inbox directory exists
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing files on startup
    event_handler = ZipFileHandler()

    existing_zips = list(settings.inbox_dir.glob("*.zip"))
    if existing_zips:
        logger.info(f"Found {len(existing_zips)} existing ZIP files on startup")
        for zip_path in existing_zips:
            # Simulate creation event for existing files
            class FakeEvent:
                def __init__(self, path):
                    self.src_path = str(path)
                    self.is_directory = False

            event_handler.on_created(FakeEvent(zip_path))

    # Start watchdog observer
    observer = Observer()
    observer.schedule(event_handler, str(settings.inbox_dir), recursive=False)
    observer.start()

    logger.info("Watcher started, monitoring for new ZIP files...")

    try:
        while True:
            time.sleep(1)
            event_handler.check_stable_files()
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Watcher stopped by user")
    except Exception as e:
        logger.exception(f"Watcher error: {e}")
        observer.stop()
        raise

    observer.join()
