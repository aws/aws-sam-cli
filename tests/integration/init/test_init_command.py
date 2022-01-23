from samcli.lib.utils.osutils import stderr
from unittest import TestCase

from parameterized import parameterized
from subprocess import STDOUT, Popen, TimeoutExpired, PIPE
import os
import shutil
import tempfile
from samcli.lib.utils.packagetype import IMAGE, ZIP

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
                    "--architecture",
                    "arm64",
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

    def test_init_command_passes_and_dir_created_image(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--package-type",
                    IMAGE,
                    "--base-image",
                    "amazon/nodejs10.x-base",
                    "--dependency-manager",
                    "npm",
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

    def test_init_command_passes_with_arm_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
                    "--dependency-manager",
                    "npm",
                    "--app-template",
                    "hello-world",
                    "--name",
                    "sam-app",
                    "--no-interactive",
                    "-o",
                    temp,
                    "--architecture",
                    "arm64",
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())

    def test_init_command_passes_with_x86_64_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
                    "--dependency-manager",
                    "npm",
                    "--app-template",
                    "hello-world",
                    "--name",
                    "sam-app",
                    "--no-interactive",
                    "-o",
                    temp,
                    "--architecture",
                    "x86_64",
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())

    def test_init_command_passes_with_unknown_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
                    "--dependency-manager",
                    "npm",
                    "--app-template",
                    "hello-world",
                    "--name",
                    "sam-app",
                    "--no-interactive",
                    "-o",
                    temp,
                    "--architecture",
                    "unknown_arch",
                ]
            )
            capture_output = ""
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired as e:
                capture_output = e.output
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            msg = "Invalid value for '-a' / '--architecture': invalid choice: unknown_arch. (choose from arm64, x86_64)"
            self.assertIn(capture_output, msg)


class TestInitForParametersCompatibility(TestCase):
    def test_init_command_no_interactive_missing_name(self):
        stderr = None
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
                    "--no-interactive",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
            Error: 
Missing required parameters, with --no-interactive set.

Must provide one of the following required parameter combinations:
    --name and --runtime and --dependency-manager and --app-template
    --name and --package-type and --base-image and --dependency-manager
    --location

You can also re-run without the --no-interactive flag to be prompted for required values.
            """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_apptemplate_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--app-template",
                    "hello-world",
                    "--no-interactive",
                    "--location",
                    "some_location",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
                        Error: 
You must not provide both the --app-template and --location parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template and --dependency-manager
    --name and --package-type and --base-image
    --location
                        """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_runtime_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--runtime",
                    "nodejs10.x",
                    "--no-interactive",
                    "--location",
                    "some_location",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
                        Error: 
You must not provide both the --runtime and --location parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template and --dependency-manager
    --name and --package-type and --base-image
    --location
                        """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_base_image_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--base-image",
                    "amazon/nodejs10.x-base",
                    "--no-interactive",
                    "--location",
                    "some_location",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
                        Error: 
You must not provide both the --base-image and --location parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template and --dependency-manager
    --name and --package-type and --base-image
    --location
                        """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_base_image_no_dependency(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--package-type",
                    IMAGE,
                    "--base-image",
                    "amazon/nodejs10.x-base",
                    "--no-interactive",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
                        Error: 
Missing required parameters, with --no-interactive set.

Must provide one of the following required parameter combinations:
    --name and --runtime and --dependency-manager and --app-template
    --name and --package-type and --base-image and --dependency-manager
    --location

You can also re-run without the --no-interactive flag to be prompted for required values.
                        """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_packagetype_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--package-type",
                    ZIP,
                    "--no-interactive",
                    "--location",
                    "some_location",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
                        Error: 
You must not provide both the --package-type and --location parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template and --dependency-manager
    --name and --package-type and --base-image
    --location
                        """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_base_image_no_packagetype(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--base-image",
                    "amazon/nodejs10.x-base",
                    "--no-interactive",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
                        Error: 
Missing required parameters, with --no-interactive set.

Must provide one of the following required parameter combinations:
    --name and --runtime and --dependency-manager and --app-template
    --name and --package-type and --base-image and --dependency-manager
    --location

You can also re-run without the --no-interactive flag to be prompted for required values.
                        """

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_wrong_packagetype(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    _get_command(),
                    "init",
                    "--package-type",
                    "WrongPT",
                    "-o",
                    temp,
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            try:
                stdout_data, stderr_data = process.communicate(timeout=TIMEOUT)
                stderr = stderr_data.decode("utf-8")
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 2)
            errmsg = """
Usage: {0} init [OPTIONS]
Try '{0} init -h' for help.

Error: Invalid value for '-p' / '--package-type': invalid choice: WrongPT. (choose from Zip, Image)
                        """.format(
                _get_command()
            )

            self.assertEqual(errmsg.strip(), "\n".join(stderr.strip().splitlines()))


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
