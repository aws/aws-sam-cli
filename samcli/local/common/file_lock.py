"""
File-based locking mechanism for preventing concurrent operations.
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

LOG = logging.getLogger(__name__)

# Default lock constants
DEFAULT_LOCK_TIMEOUT = 300  # 5 minutes timeout
DEFAULT_LOCK_POLL_INTERVAL = 2  # Poll every 2 seconds

# Status constants
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class FileLock:
    """
    File-based locking mechanism to prevent concurrent operations on the same resource.

    This class provides a generic file-based locking mechanism that can be used to prevent
    concurrent operations like downloads, builds, or any other resource-intensive tasks
    that should not run simultaneously for the same resource.
    """

    def __init__(
        self,
        lock_dir: Path,
        resource_name: str,
        operation_name: str = "operation",
        timeout: int = DEFAULT_LOCK_TIMEOUT,
        poll_interval: int = DEFAULT_LOCK_POLL_INTERVAL,
    ):
        """
        Initialize the file lock for a specific resource and operation.

        Parameters
        ----------
        lock_dir : Path
            Directory to store lock files
        resource_name : str
            The resource name being operated on (used to create unique lock file)
        operation_name : str
            The operation name (e.g., "downloading", "building")
        timeout : int
            Timeout in seconds for waiting for locks
        poll_interval : int
            Polling interval in seconds when waiting for locks
        """
        self.lock_dir = Path(lock_dir)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self.operation_name = operation_name
        self.timeout = timeout
        self.poll_interval = poll_interval

        # Create a safe filename from the resource name
        safe_name = re.sub(r"[^\w\-_.]", "_", resource_name.replace(":", "_").replace("/", "_"))
        self.lock_file = self.lock_dir / f"{safe_name}.{operation_name}.lock"
        self.status_file = self.lock_dir / f"{safe_name}.{operation_name}.status"
        self.process_id = os.getpid()

    def acquire_lock(self) -> bool:
        """
        Attempt to acquire the operation lock.

        Returns
        -------
        bool
            True if lock was acquired, False if another process is performing the operation
        """
        try:
            # Check if lock file exists and is still valid
            if self.lock_file.exists():
                lock_age = time.time() - self.lock_file.stat().st_mtime
                if lock_age > self.timeout:
                    LOG.warning(f"Removing stale {self.operation_name} lock file: {self.lock_file}")
                    self._cleanup_lock_files()
                else:
                    return False

            # Create lock file with process ID
            with open(self.lock_file, "w") as f:
                f.write(f"{self.process_id}\n{time.time()}")

            # Set status to in progress
            self._set_status(STATUS_IN_PROGRESS)
            return True

        except (OSError, IOError) as e:
            LOG.warning(f"Failed to acquire {self.operation_name} lock: {e}")
            return False

    def release_lock(self, success: bool = True):
        """
        Release the operation lock and set final status.

        Parameters
        ----------
        success : bool
            Whether the operation was successful
        """
        try:
            status = STATUS_COMPLETED if success else STATUS_FAILED
            self._set_status(status)

            if self.lock_file.exists():
                self.lock_file.unlink()

        except (OSError, IOError) as e:
            LOG.warning(f"Failed to release {self.operation_name} lock: {e}")

    def wait_for_operation(self) -> bool:
        """
        Wait for another process to complete the operation.

        Returns
        -------
        bool
            True if operation completed successfully, False if failed or timed out
        """
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            # Check if lock file is gone (operation completed)
            if not self.lock_file.exists():
                status = self._get_status()
                if status == STATUS_COMPLETED:
                    return True
                elif status == STATUS_FAILED:
                    return False
                # If no status file, assume completed (backward compatibility)
                return True

            # Check if lock is stale
            if self.lock_file.exists():
                lock_age = time.time() - self.lock_file.stat().st_mtime
                if lock_age > self.timeout:
                    LOG.warning(f"{self.operation_name.capitalize()} lock appears stale, proceeding")
                    self._cleanup_lock_files()
                    return False

            LOG.info(f"Waiting for concurrent {self.operation_name} to complete... ({int(time.time() - start_time)}s)")
            time.sleep(self.poll_interval)

        LOG.warning(f"Timeout waiting for concurrent {self.operation_name}, proceeding")
        self._cleanup_lock_files()
        return False

    def _set_status(self, status: str):
        """Set the operation status."""
        try:
            with open(self.status_file, "w") as f:
                f.write(f"{status}\n{time.time()}")
        except (OSError, IOError) as e:
            LOG.warning(f"Failed to set {self.operation_name} status: {e}")

    def _get_status(self) -> Optional[str]:
        """Get the current operation status."""
        try:
            if self.status_file.exists():
                with open(self.status_file, "r") as f:
                    return f.readline().strip()
        except (OSError, IOError) as e:
            LOG.warning(f"Failed to read {self.operation_name} status: {e}")
        return None

    def _cleanup_lock_files(self):
        """Clean up lock and status files."""
        try:
            if self.lock_file.exists():
                self.lock_file.unlink()
            if self.status_file.exists():
                self.status_file.unlink()
        except (OSError, IOError) as e:
            LOG.warning(f"Failed to cleanup {self.operation_name} lock files: {e}")


def cleanup_stale_locks(lock_dir: Path, operation_name: str, timeout: int = DEFAULT_LOCK_TIMEOUT):
    """
    Clean up old lock files that may have been left behind by crashed processes.

    Parameters
    ----------
    lock_dir : Path
        Directory containing lock files
    operation_name : str
        The operation name to clean up locks for
    timeout : int
        Age threshold for considering locks stale
    """
    try:
        # Handle case where lock_dir might be a mock in tests
        if not hasattr(lock_dir, "exists") or not hasattr(lock_dir, "glob"):
            return

        if not lock_dir.exists():
            return

        current_time = time.time()
        lock_pattern = f"*.{operation_name}.lock"

        for lock_file in lock_dir.glob(lock_pattern):
            try:
                # Remove locks older than timeout period
                if current_time - lock_file.stat().st_mtime > timeout:
                    LOG.debug(f"Removing stale {operation_name} lock file: {lock_file}")
                    lock_file.unlink()

                    # Also remove corresponding status file
                    status_file = lock_file.with_suffix(".status")
                    if status_file.exists():
                        status_file.unlink()

            except (OSError, IOError) as e:
                LOG.debug(f"Failed to remove stale {operation_name} lock file {lock_file}: {e}")

    except (OSError, IOError, TypeError) as e:
        LOG.debug(f"Failed to cleanup stale {operation_name} locks in {lock_dir}: {e}")
