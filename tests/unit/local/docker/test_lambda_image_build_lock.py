"""
Tests for ImageBuildLock functionality in lambda_image.py
"""

import os
import tempfile
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch, mock_open

from samcli.local.common.file_lock import (
    FileLock,
    DEFAULT_LOCK_TIMEOUT,
    DEFAULT_LOCK_POLL_INTERVAL,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_FAILED,
)


class TestImageBuildLock(TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.image_tag = "test-image:latest"
        self.build_lock = FileLock(self.temp_dir, self.image_tag, "building")

    def tearDown(self):
        # Clean up any created files
        try:
            if self.build_lock.lock_file.exists():
                self.build_lock.lock_file.unlink()
            if self.build_lock.status_file.exists():
                self.build_lock.status_file.unlink()
            self.temp_dir.rmdir()
        except (OSError, IOError):
            pass

    def test_initialization(self):
        """Test ImageBuildLock initialization"""
        self.assertTrue(self.temp_dir.exists())
        self.assertEqual(self.build_lock.process_id, os.getpid())
        self.assertTrue(self.build_lock.lock_file.name.endswith(".building.lock"))
        self.assertTrue(self.build_lock.status_file.name.endswith(".status"))

    def test_acquire_lock_success(self):
        """Test successful lock acquisition"""
        result = self.build_lock.acquire_lock()
        self.assertTrue(result)
        self.assertTrue(self.build_lock.lock_file.exists())
        self.assertTrue(self.build_lock.status_file.exists())

    def test_acquire_lock_already_exists_fresh(self):
        """Test lock acquisition when lock file already exists and is fresh"""
        # Create a fresh lock file
        with open(self.build_lock.lock_file, "w") as f:
            f.write(f"{os.getpid()}\n{time.time()}")

        result = self.build_lock.acquire_lock()
        self.assertFalse(result)

    @patch("time.time")
    def test_acquire_lock_stale_lock_removed(self, mock_time):
        """Test that stale lock files are removed"""
        current_time = 1000.0
        stale_time = current_time - DEFAULT_LOCK_TIMEOUT - 1
        mock_time.return_value = current_time

        # Create a stale lock file
        with open(self.build_lock.lock_file, "w") as f:
            f.write(f"{os.getpid()}\n{stale_time}")

        # Set the file modification time to be stale
        os.utime(self.build_lock.lock_file, (stale_time, stale_time))

        with patch("samcli.local.common.file_lock.LOG") as mock_log:
            result = self.build_lock.acquire_lock()
            self.assertTrue(result)
            mock_log.warning.assert_called_once()

    def test_acquire_lock_io_error(self):
        """Test lock acquisition with IO error"""
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with patch("samcli.local.common.file_lock.LOG") as mock_log:
                result = self.build_lock.acquire_lock()
                self.assertFalse(result)
                mock_log.warning.assert_called_once()

    def test_release_lock_success(self):
        """Test successful lock release"""
        # First acquire the lock
        self.build_lock.acquire_lock()
        self.assertTrue(self.build_lock.lock_file.exists())

        # Then release it
        self.build_lock.release_lock(success=True)
        self.assertFalse(self.build_lock.lock_file.exists())
        self.assertTrue(self.build_lock.status_file.exists())

    def test_release_lock_failure(self):
        """Test lock release with failure status"""
        self.build_lock.acquire_lock()
        self.build_lock.release_lock(success=False)

        # Check status is set to failed
        status = self.build_lock._get_status()
        self.assertEqual(status, STATUS_FAILED)

    def test_release_lock_io_error(self):
        """Test lock release with IO error"""
        self.build_lock.acquire_lock()

        with patch.object(Path, "unlink", side_effect=IOError("Permission denied")):
            with patch("samcli.local.common.file_lock.LOG") as mock_log:
                self.build_lock.release_lock()
                mock_log.warning.assert_called_once()

    def test_wait_for_build_completed(self):
        """Test waiting for build that completes successfully"""

        # Simulate lock file being removed (build completed)
        def side_effect():
            if self.build_lock.lock_file.exists():
                self.build_lock.lock_file.unlink()
            self.build_lock._set_status(STATUS_COMPLETED)

        with patch("time.sleep", side_effect=side_effect):
            result = self.build_lock.wait_for_operation()
            self.assertTrue(result)

    def test_wait_for_build_failed(self):
        """Test waiting for build that fails"""
        # First set the failed status, then remove lock file
        self.build_lock._set_status(STATUS_FAILED)

        # Simulate lock file being removed
        def side_effect():
            if self.build_lock.lock_file.exists():
                self.build_lock.lock_file.unlink()

        with patch("time.sleep", side_effect=side_effect):
            result = self.build_lock.wait_for_operation()
            self.assertFalse(result)

    def test_wait_for_build_no_status_file(self):
        """Test waiting for build with no status file (backward compatibility)"""

        # Simulate lock file being removed without status file
        def side_effect():
            if self.build_lock.lock_file.exists():
                self.build_lock.lock_file.unlink()

        with patch("time.sleep", side_effect=side_effect):
            result = self.build_lock.wait_for_operation()
            self.assertTrue(result)

    @patch("time.time")
    def test_wait_for_build_stale_lock(self, mock_time):
        """Test waiting for build with stale lock"""
        current_time = 1000.0
        stale_time = current_time - DEFAULT_LOCK_TIMEOUT - 1
        mock_time.return_value = current_time

        # Create a stale lock file
        with open(self.build_lock.lock_file, "w") as f:
            f.write(f"{os.getpid()}\n{stale_time}")
        os.utime(self.build_lock.lock_file, (stale_time, stale_time))

        with patch("samcli.local.common.file_lock.LOG") as mock_log:
            with patch("time.sleep"):
                result = self.build_lock.wait_for_operation()
                self.assertFalse(result)
                mock_log.warning.assert_called()

    @patch("time.time")
    def test_wait_for_build_timeout(self, mock_time):
        """Test waiting for build that times out"""
        # Mock time to simulate timeout
        start_time = 1000.0
        timeout_time = start_time + DEFAULT_LOCK_TIMEOUT + 1
        mock_time.side_effect = [start_time, timeout_time]

        # Create a persistent lock file
        with open(self.build_lock.lock_file, "w") as f:
            f.write(f"{os.getpid()}\n{start_time}")

        with patch("samcli.local.common.file_lock.LOG") as mock_log:
            with patch("time.sleep"):
                result = self.build_lock.wait_for_operation()
                self.assertFalse(result)
                mock_log.warning.assert_called()

    def test_set_status_success(self):
        """Test setting status successfully"""
        self.build_lock._set_status(STATUS_IN_PROGRESS)
        self.assertTrue(self.build_lock.status_file.exists())

        status = self.build_lock._get_status()
        self.assertEqual(status, STATUS_IN_PROGRESS)

    def test_set_status_io_error(self):
        """Test setting status with IO error"""
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with patch("samcli.local.common.file_lock.LOG") as mock_log:
                self.build_lock._set_status(STATUS_IN_PROGRESS)
                mock_log.warning.assert_called_once()

    def test_get_status_no_file(self):
        """Test getting status when no status file exists"""
        status = self.build_lock._get_status()
        self.assertIsNone(status)

    def test_get_status_io_error(self):
        """Test getting status with IO error"""
        # Create status file first
        self.build_lock._set_status(STATUS_IN_PROGRESS)

        with patch("builtins.open", side_effect=IOError("Permission denied")):
            status = self.build_lock._get_status()
            self.assertIsNone(status)

    def test_cleanup_lock_files_success(self):
        """Test successful cleanup of lock files"""
        # Create both files
        self.build_lock.acquire_lock()
        self.assertTrue(self.build_lock.lock_file.exists())
        self.assertTrue(self.build_lock.status_file.exists())

        # Clean them up
        self.build_lock._cleanup_lock_files()
        self.assertFalse(self.build_lock.lock_file.exists())
        self.assertFalse(self.build_lock.status_file.exists())

    def test_cleanup_lock_files_io_error(self):
        """Test cleanup with IO error"""
        self.build_lock.acquire_lock()

        with patch.object(Path, "unlink", side_effect=IOError("Permission denied")):
            with patch("samcli.local.common.file_lock.LOG") as mock_log:
                self.build_lock._cleanup_lock_files()
                mock_log.warning.assert_called()

    def test_cleanup_lock_files_partial_exists(self):
        """Test cleanup when only some files exist"""
        # Create only lock file
        with open(self.build_lock.lock_file, "w") as f:
            f.write("test")

        self.build_lock._cleanup_lock_files()
        self.assertFalse(self.build_lock.lock_file.exists())
