"""
Unit tests for the FileLock class
"""

import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from samcli.local.common.file_lock import FileLock, cleanup_stale_locks


class TestFileLock(TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.resource_name = "test_resource"
        self.operation_name = "testing"

    def tearDown(self):
        # Clean up any lock files
        for lock_file in self.temp_dir.glob("*.lock"):
            lock_file.unlink()
        for status_file in self.temp_dir.glob("*.status"):
            status_file.unlink()
        self.temp_dir.rmdir()

    def test_acquire_and_release_lock(self):
        """Test basic lock acquisition and release"""
        lock = FileLock(self.temp_dir, self.resource_name, self.operation_name)

        # Should be able to acquire lock
        self.assertTrue(lock.acquire_lock())

        # Lock file should exist
        self.assertTrue(lock.lock_file.exists())
        self.assertTrue(lock.status_file.exists())

        # Release lock
        lock.release_lock(success=True)

        # Lock file should be gone
        self.assertFalse(lock.lock_file.exists())

    def test_concurrent_lock_acquisition(self):
        """Test that only one process can acquire the lock"""
        lock1 = FileLock(self.temp_dir, self.resource_name, self.operation_name)
        lock2 = FileLock(self.temp_dir, self.resource_name, self.operation_name)

        # First lock should succeed
        self.assertTrue(lock1.acquire_lock())

        # Second lock should fail
        self.assertFalse(lock2.acquire_lock())

        # Release first lock
        lock1.release_lock(success=True)

        # Now second lock should succeed
        self.assertTrue(lock2.acquire_lock())

        lock2.release_lock(success=True)

    def test_wait_for_operation(self):
        """Test waiting for another operation to complete"""
        lock1 = FileLock(self.temp_dir, self.resource_name, self.operation_name, timeout=5, poll_interval=1)
        lock2 = FileLock(self.temp_dir, self.resource_name, self.operation_name, timeout=5, poll_interval=1)

        # Acquire first lock
        self.assertTrue(lock1.acquire_lock())

        # Start a timer to release the lock after 2 seconds
        def release_after_delay():
            time.sleep(2)
            lock1.release_lock(success=True)

        import threading

        release_thread = threading.Thread(target=release_after_delay)
        release_thread.start()

        # Wait for operation should succeed
        start_time = time.time()
        result = lock2.wait_for_operation()
        elapsed = time.time() - start_time

        self.assertTrue(result)
        self.assertGreaterEqual(elapsed, 2)  # Should have waited at least 2 seconds
        self.assertLess(elapsed, 4)  # But not too long

        release_thread.join()

    def test_stale_lock_cleanup(self):
        """Test cleanup of stale locks"""
        import os

        lock = FileLock(self.temp_dir, self.resource_name, self.operation_name)

        # Create a lock file manually with old timestamp
        lock.lock_file.touch()
        lock.status_file.touch()

        # Modify the timestamp to make it appear old
        old_time = time.time() - 400  # 400 seconds ago (older than default timeout)
        os.utime(lock.lock_file, (old_time, old_time))

        # Cleanup should remove the stale lock
        cleanup_stale_locks(self.temp_dir, self.operation_name, timeout=300)

        self.assertFalse(lock.lock_file.exists())
        self.assertFalse(lock.status_file.exists())

    def test_safe_filename_generation(self):
        """Test that unsafe characters in resource names are handled"""
        unsafe_name = "my:resource/with\\unsafe*chars"
        lock = FileLock(self.temp_dir, unsafe_name, self.operation_name)

        # Should be able to acquire lock without issues
        self.assertTrue(lock.acquire_lock())

        # Lock file should exist with safe name
        self.assertTrue(lock.lock_file.exists())

        lock.release_lock(success=True)

    @patch("samcli.local.common.file_lock.LOG")
    def test_cleanup_with_mock_path(self, mock_log):
        """Test cleanup function handles mocked Path objects gracefully"""
        from unittest.mock import Mock

        mock_path = Mock()
        mock_path.exists.return_value = False

        # Should not raise an exception
        cleanup_stale_locks(mock_path, self.operation_name)

        # Should handle case where path doesn't have required methods
        mock_path_no_methods = Mock(spec=[])
        cleanup_stale_locks(mock_path_no_methods, self.operation_name)
