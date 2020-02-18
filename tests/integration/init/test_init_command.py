from unittest import TestCase

from parameterized import parameterized
from subprocess import Popen, TimeoutExpired
import os
import shutil
import tempfile

from pathlib import Path

TIMEOUT = 300


class TestBasicInitCommand(TestCase):
    def test_init_command_passes_and_dir_created(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
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
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())

    def test_init_new_app_template(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
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
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "qs-scratch").is_dir())

    def test_init_command_java_maven(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
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
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app-maven").is_dir())

    def test_init_command_java_gradle(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
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
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app-gradle").is_dir())

    def test_init_command_with_extra_context_parameter(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
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
                    "--extra-context",
                    '{"schema_name": "codedeploy", "schema_type": "aws"}',
                    "-o",
                    temp,
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app-maven").is_dir())


class TestInitWithArbitraryProject(TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

        zipdata_folder = Path(self.tempdir, "zipdata")
        zipdata_folder.mkdir(parents=True)
        Path(zipdata_folder, "test.txt").write_text("hello world")

        zip_path_no_extension = str(Path(self.tempdir, "myfile"))

        self.zip_path = shutil.make_archive(zip_path_no_extension, "zip", root_dir=self.tempdir, base_dir="zipdata")

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    @parameterized.expand([(None,), ("project_name",)])
    def test_arbitrary_project(self, project_name):
        with tempfile.TemporaryDirectory() as temp:
            args = [_get_command(), "init", "--location", self.zip_path, "-o", temp]
            if project_name:
                args.extend(["--name", project_name])

            process = Popen(args)
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            expected_output_folder = Path(temp, project_name) if project_name else Path(temp)
            self.assertEqual(process.returncode, 0)
            self.assertTrue(expected_output_folder.exists())
            self.assertEqual(os.listdir(str(expected_output_folder)), ["test.txt"])
            self.assertEqual(Path(expected_output_folder, "test.txt").read_text(), "hello world")

    def test_zip_not_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            args = [_get_command(), "init", "--location", str(Path("invalid", "zip", "path")), "-o", temp]

            process = Popen(args)
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 1)


def _get_command():
    command = "sam"
    if os.getenv("SAM_CLI_DEV"):
        command = "samdev"
    return command
