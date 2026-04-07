"""
Unit tests for rapid binary validation
"""

import os
from unittest import TestCase


class TestRapidBinaryPermissions(TestCase):
    def test_rapid_binaries_are_executable(self):
        """Test that all rapid binaries have executable permissions"""
        rapid_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "samcli", "local", "rapid")

        expected_binaries = [
            "aws-lambda-rie-x86_64",
            "aws-lambda-rie-arm64",
            "aws-durable-execution-emulator-x86_64",
            "aws-durable-execution-emulator-arm64",
        ]

        for binary_name in expected_binaries:
            binary_path = os.path.join(rapid_dir, binary_name)

            with self.subTest(binary=binary_name):
                self.assertTrue(os.path.exists(binary_path), f"Binary {binary_name} does not exist")
                self.assertTrue(os.access(binary_path, os.X_OK), f"Binary {binary_name} is not executable")
