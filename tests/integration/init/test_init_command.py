from unittest import TestCase
from subprocess import Popen
import os
import tempfile


class TestBasicInitCommand(TestCase):
    def test_init_command_passes_and_dir_created(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    TestBasicInitCommand._get_command(),
                    "init",
                    "--runtime",
                    "nodejs10.x",
                    "--dependency-manager",
                    "npm",
                    "--app-template",
                    "hello-world",
                    "--name",
                    "sam-app",
                    "--no-interactive",
                    "-o",
                    temp,
                ]
            )
            return_code = process.wait()

            self.assertEqual(return_code, 0)
            self.assertTrue(os.path.isdir(temp + "/sam-app"))

    def test_init_new_app_template(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    TestBasicInitCommand._get_command(),
                    "init",
                    "--runtime",
                    "nodejs10.x",
                    "--dependency-manager",
                    "npm",
                    "--app-template",
                    "quick-start-from-scratch",
                    "--name",
                    "qs-scratch",
                    "--no-interactive",
                    "-o",
                    temp,
                ]
            )
            return_code = process.wait()

            self.assertEqual(return_code, 0)
            self.assertTrue(os.path.isdir(temp + "/qs-scratch"))

    def test_init_command_java_maven(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    TestBasicInitCommand._get_command(),
                    "init",
                    "--runtime",
                    "java8",
                    "--dependency-manager",
                    "maven",
                    "--app-template",
                    "hello-world",
                    "--name",
                    "sam-app-maven",
                    "--no-interactive",
                    "-o",
                    temp,
                ]
            )
            return_code = process.wait()

            self.assertEqual(return_code, 0)
            self.assertTrue(os.path.isdir(temp + "/sam-app-maven"))

    def test_init_command_java_gradle(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    TestBasicInitCommand._get_command(),
                    "init",
                    "--runtime",
                    "java8",
                    "--dependency-manager",
                    "gradle",
                    "--app-template",
                    "hello-world",
                    "--name",
                    "sam-app-gradle",
                    "--no-interactive",
                    "-o",
                    temp,
                ]
            )
            return_code = process.wait()

            self.assertEqual(return_code, 0)
            self.assertTrue(os.path.isdir(temp + "/sam-app-gradle"))

    @staticmethod
    def _get_command():
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command
