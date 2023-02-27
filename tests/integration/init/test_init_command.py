import platform
import time
import signal

from click.testing import CliRunner

from samcli.commands.init import cli as init_cmd
from unittest import TestCase

from parameterized import parameterized
from subprocess import Popen, TimeoutExpired, PIPE
import os
import shutil
import tempfile

from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME
from samcli.lib.utils.packagetype import IMAGE, ZIP

from pathlib import Path

from tests.integration.init.test_init_base import InitIntegBase
from tests.testing_utils import get_sam_command

TIMEOUT = 300

COMMIT_ERROR = "WARN: Commit not exist:"


class TestBasicInitCommand(TestCase):
    def test_init_command_passes_and_dir_created(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_passes_and_dir_created_image(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--package-type",
                    IMAGE,
                    "--base-image",
                    "amazon/nodejs14.x-base",
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
                    get_sam_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
                    "--dependency-manager",
                    "npm",
                    "--app-template",
                    "quick-start-from-scratch",
                    "--name",
                    "qs-scratch",
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "qs-scratch").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_java_maven(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app-maven").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_java_gradle(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app-gradle").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_with_extra_context_parameter(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app-maven").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_passes_with_arm_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_passes_with_x86_64_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)

    def test_init_command_passes_with_unknown_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

    def test_init_command_passes_with_enabled_tracing(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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
                    "--tracing",
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())

    def test_init_command_passes_with_disabled_tracing(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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
                    "--no-tracing",
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())

    def test_init_command_passes_with_enabled_application_insights(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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
                    "--application-insights",
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())

    def test_init_command_passes_with_disabled_application_insights(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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
                    "--no-application-insights",
                ]
            )
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self.assertTrue(Path(temp, "sam-app").is_dir())


MISSING_REQUIRED_PARAM_MESSAGE = """Error: Missing required parameters, with --no-interactive set.
Must provide one of the following required parameter combinations:
\t--name, --location
\t--name, --package-type, --base-image
\t--name, --runtime, --dependency-manager, --app-template
You can also re-run without the --no-interactive flag to be prompted for required values.
"""

INCOMPATIBLE_PARAM_MESSAGE = """Error: You must not provide both the --{0} and --{1} parameters.
You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
\t--name, --location, or
\t--name, --package-type, --base-image, or
\t--name, --runtime, --app-template, --dependency-manager
"""


class TestInitForParametersCompatibility(TestCase):
    def test_init_command_no_interactive_missing_name(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
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

            self.assertIn(MISSING_REQUIRED_PARAM_MESSAGE.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_apptemplate_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertIn(
                INCOMPATIBLE_PARAM_MESSAGE.strip().format("app-template", "location"),
                "\n".join(stderr.strip().splitlines()),
            )

    def test_init_command_no_interactive_runtime_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
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

            self.assertIn(
                INCOMPATIBLE_PARAM_MESSAGE.strip().format("runtime", "location"), "\n".join(stderr.strip().splitlines())
            )

    def test_init_command_no_interactive_base_image_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--base-image",
                    "amazon/nodejs14.x-base",
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

            self.assertIn(
                INCOMPATIBLE_PARAM_MESSAGE.strip().format("base-image", "location"),
                "\n".join(stderr.strip().splitlines()),
            )

    def test_init_command_no_interactive_base_image_no_dependency(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--package-type",
                    IMAGE,
                    "--base-image",
                    "amazon/nodejs14.x-base",
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

            self.assertIn(MISSING_REQUIRED_PARAM_MESSAGE.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_no_interactive_packagetype_location(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

            self.assertIn(
                INCOMPATIBLE_PARAM_MESSAGE.strip().format("package-type", "location"),
                "\n".join(stderr.strip().splitlines()),
            )

    def test_init_command_no_interactive_base_image_no_packagetype(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--base-image",
                    "amazon/nodejs14.x-base",
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

            self.assertIn(MISSING_REQUIRED_PARAM_MESSAGE.strip(), "\n".join(stderr.strip().splitlines()))

    def test_init_command_wrong_packagetype(self):
        stderr = None
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
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

Error: Invalid value for '-p' / '--package-type': 'WrongPT' is not one of 'Zip', 'Image'.
                        """.format(
                get_sam_command()
            )

            self.assertIn(errmsg.strip(), "\n".join(stderr.strip().splitlines()))


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

    def _validate_expected_files_exist(self, output_folder: Path, config_exists: bool = True):
        self.assertTrue(output_folder.exists())
        self.assertEqual(
            set(os.listdir(str(output_folder))),
            set(["test.txt"] + [DEFAULT_CONFIG_FILE_NAME] if config_exists else ["test.txt"]),
        )
        self.assertEqual(Path(output_folder, "test.txt").read_text(), "hello world")

    @parameterized.expand([(None,), ("project_name",)])
    def test_arbitrary_project(self, project_name):
        with tempfile.TemporaryDirectory() as temp:
            args = [get_sam_command(), "init", "--location", self.zip_path, "-o", temp]
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
            self._validate_expected_files_exist(expected_output_folder, config_exists=True if project_name else False)

    def test_zip_not_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            args = [get_sam_command(), "init", "--location", str(Path("invalid", "zip", "path")), "-o", temp]

            process = Popen(args)
            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 1)

    def test_location_with_no_interactive_and_name(self):
        project_name = "test-project"

        with tempfile.TemporaryDirectory() as tmp:
            args = [
                get_sam_command(),
                "init",
                "--name",
                project_name,
                "--location",
                self.zip_path,
                "--no-interactive",
                "-o",
                tmp,
            ]
            process = Popen(args)

            try:
                process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise

            self.assertEqual(process.returncode, 0)
            self._validate_expected_files_exist(Path(tmp, project_name))


class TestInteractiveInit(TestCase):
    def test_interactive_init(self):
        # 1: AWS Quick Start Templates
        # 1: Hello World Example
        # N: Use the most popular runtime and package type? (Python and zip) [y/N]
        # 12: nodejs16.x
        # 1: Zip
        # 1: Hello World Example
        # N: Would you like to enable X-Ray tracing on the function(s) in your application?  [y/N]
        # Y: Would you like to enable monitoring using Cloudwatch Application Insights? [y/N]
        user_input = """
1
1
N
13
1
1
N
Y
sam-interactive-init-app
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp, "--debug"], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "sam-interactive-init-app")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello-world").is_dir())
            self.assertTrue(Path(expected_output_folder, "hello-world", "app.js").is_file())

    def test_interactive_init_default_runtime(self):
        user_input = """
1
1
Y
N
N
sam-interactive-init-app-default-runtime
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp, "--debug"], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "sam-interactive-init-app-default-runtime")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world").is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world", "app.py").is_file())


class TestInitProducesSamconfigFile(TestCase):
    def test_zip_template_config(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--runtime",
                    "nodejs14.x",
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

            project_directory = Path(temp, "sam-app")

            self.assertEqual(process.returncode, 0)
            self.assertTrue(project_directory.is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)
            self._validate_zip_samconfig(project_directory)

    def test_image_template_config(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Popen(
                [
                    get_sam_command(),
                    "init",
                    "--package-type",
                    IMAGE,
                    "--base-image",
                    "amazon/nodejs14.x-base",
                    "--dependency-manager",
                    "npm",
                    "--name",
                    "sam-app",
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

            project_directory = Path(temp, "sam-app")

            self.assertEqual(process.returncode, 0)
            self.assertTrue(project_directory.is_dir())
            self.assertNotIn(COMMIT_ERROR, stderr)
            self._validate_image_samconfig(project_directory)

    def _validate_image_samconfig(self, project_path):
        text = self._read_config(project_path)

        self._validate_common_properties(text)

        self.assertFalse(self._check_property("cached = true", text))
        self.assertTrue(self._check_property("resolve_s3 = true", text))
        self.assertTrue(self._check_property("resolve_image_repos = true", text))

    def _validate_zip_samconfig(self, project_path):
        text = self._read_config(project_path)

        self._validate_common_properties(text)

        self.assertTrue(self._check_property("cached = true", text))
        self.assertTrue(self._check_property("resolve_s3 = true", text))
        self.assertFalse(self._check_property("resolve_image_repos = true", text))

    def _validate_common_properties(self, text):
        self.assertTrue(self._check_property("parallel = true", text))
        self.assertTrue(self._check_property('warm_containers = "EAGER"', text))
        self.assertTrue(self._check_property('stack_name = "sam-app"', text))
        self.assertTrue(self._check_property("watch = true", text))
        self.assertTrue(self._check_property('capabilities = "CAPABILITY_IAM"', text))

    @staticmethod
    def _check_property(to_find, container):
        return any(to_find in line for line in container)

    @staticmethod
    def _read_config(project_path):
        with open(Path(project_path, "samconfig.toml"), "r") as f:
            text = f.readlines()
        return text


class TestInitCommand(InitIntegBase):
    def test_graceful_exit(self):
        # Run the Base Command
        command_list = self.get_command()
        process_execute = Popen(command_list, stdout=PIPE, stderr=PIPE)

        # Wait for binary to be ready before sending interrupts.
        time.sleep(self.BINARY_READY_WAIT_TIME)

        # Send SIGINT signal
        process_execute.send_signal(signal.CTRL_C_EVENT if platform.system().lower() == "windows" else signal.SIGINT)
        process_execute.wait()
        # Process should exit gracefully with an exit code of 1.
        self.assertEqual(process_execute.returncode, 1)
        self.assertIn("Aborted!", process_execute.stderr.read().decode("utf-8"))
