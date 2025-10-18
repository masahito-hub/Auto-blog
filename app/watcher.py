"""File watcher for monitoring ZIP files in inbox directory."""

import logging
import time
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
        self.pending_files: dict[str, float] = {}
        self.stability_timeout = 5  # seconds

    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return

        path = Path(event.src_path)
        if path.suffix.lower() != ".zip":
            return

        logger.info(f"Detected new ZIP file: {path.name}")
        self.pending_files[str(path)] = time.time()

    def check_stable_files(self):
        """Check if pending files are stable and enqueue them."""
        current_time = time.time()
        stable_files = []

        for file_path, detected_time in self.pending_files.items():
            path = Path(file_path)
            if not path.exists():
                stable_files.append(file_path)
                continue

            # Check if file size is stable
            if current_time - detected_time >= self.stability_timeout:
                try:
                    # Enqueue the job
                    job_id = enqueue_job(path)
                    logger.info(f"Enqueued job {job_id} for {path.name}")
                    stable_files.append(file_path)
                except Exception as e:
                    logger.error(f"Failed to enqueue {path.name}: {e}")
                    stable_files.append(file_path)

        # Remove processed files
        for file_path in stable_files:
            self.pending_files.pop(file_path, None)


def start_watcher():
    """Start the file watcher."""
    logger.info(f"Starting watcher on {settings.inbox_dir}")

    # Ensure inbox directory exists
    settings.inbox_dir.mkdir(parents=True, exist_ok=True)

    event_handler = ZipFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(settings.inbox_dir), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
            event_handler.check_stable_files()
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Watcher stopped")

    observer.join()
