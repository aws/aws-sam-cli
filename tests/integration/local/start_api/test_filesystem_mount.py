"""
Integration tests for --filesystem flag with start-api command
Tests that the --filesystem flag correctly mounts EFS directories and allows Lambda functions
to interact with the mounted filesystem.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
import requests

from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass


class TestFilesystemMountWithStartApi(StartApiIntegBaseClass):
    """
    Test that --filesystem flag correctly mounts EFS directories for start-api
    """

    template_path = "/testdata/start_api/filesystem/template.yaml"

    def setUp(self):
        self.url = f"http://127.0.0.1:{self.port}"

        # Create a temporary filesystem directory with test files
        self.test_fs_dir = tempfile.mkdtemp()
        self.test_file = Path(self.test_fs_dir) / "test.txt"
        self.test_file.write_text("Hello from EFS!")

    def tearDown(self):
        # Clean up test filesystem
        if os.path.exists(self.test_fs_dir):
            shutil.rmtree(self.test_fs_dir)
        super().tearDown()

    @property
    def command_list(self):
        command_list = super().command_list
        # Add filesystem flag pointing to our test directory
        command_list.extend(["--filesystem", self.test_fs_dir])
        return command_list

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_can_read_from_mounted_filesystem(self):
        """
        Test that Lambda function can read files from mounted EFS directory
        """
        response = requests.get(f"{self.url}/read-file", params={"filename": "test.txt"}, timeout=300)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("content"), "Hello from EFS!")
        self.assertEqual(data.get("success"), True)
        self.assertEqual(data.get("filename"), "test.txt")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_can_write_to_mounted_filesystem(self):
        """
        Test that Lambda function can write files to mounted EFS directory
        and verify changes persist on host filesystem
        """
        write_content = "Written from Lambda!"
        response = requests.post(
            f"{self.url}/write-file", json={"filename": "written.txt", "content": write_content}, timeout=300
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("success"), True)
        self.assertEqual(data.get("filename"), "written.txt")

        # Verify file actually exists on host filesystem
        written_file = Path(self.test_fs_dir) / "written.txt"
        self.assertTrue(written_file.exists(), "File should exist on host filesystem after Lambda write")
        self.assertEqual(written_file.read_text(), write_content, "File content should match what Lambda wrote")

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_lambda_can_list_mounted_filesystem(self):
        """
        Test that Lambda function can list directory contents of mounted EFS
        """
        response = requests.get(f"{self.url}/list-files", timeout=300)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("success"), True)
        self.assertIn("test.txt", data.get("files", []), "test.txt should be visible to Lambda in mounted filesystem")
        self.assertEqual(data.get("mount_path"), "/mnt/efs", "Mount path should be /mnt/efs")
