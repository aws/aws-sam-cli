import os
import subprocess
import tempfile

from parameterized import parameterized
from unittest import TestCase


TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "templates", "sar")

# Get all template files and sort them for consistent ordering
ALL_TEMPLATE_FILE_NAMES = sorted([v for v in os.listdir(TEMPLATE_FOLDER) if "yaml" in v])

# Check environment variable to determine which subset to use
SMOKE_TEST_SUBSET = os.environ.get("SMOKE_TEST_SUBSET", "").lower()

# Calculate split points for dividing into thirds
total_count = len(ALL_TEMPLATE_FILE_NAMES)
first_third = total_count // 3
second_third = (total_count * 2) // 3

# Adjust split points to balance load (since the third part also runs functional tests)
if second_third > 2:
    # third part will also run functional tests, distribute more tests to earlier parts
    first_third = first_third + 1
    second_third = second_third + 2

TEMPLATE_FILE_NAMES = ALL_TEMPLATE_FILE_NAMES
# Select appropriate subset based on environment variable
if SMOKE_TEST_SUBSET == "first-third":
    # Select first third of templates
    TEMPLATE_FILE_NAMES = ALL_TEMPLATE_FILE_NAMES[:first_third]
elif SMOKE_TEST_SUBSET == "second-third":
    # Select second third of templates
    TEMPLATE_FILE_NAMES = ALL_TEMPLATE_FILE_NAMES[first_third:second_third]
elif SMOKE_TEST_SUBSET == "third-third":
    # Select last third of templates
    TEMPLATE_FILE_NAMES = ALL_TEMPLATE_FILE_NAMES[second_third:]


class TestAllCommands(TestCase):
    @parameterized.expand(TEMPLATE_FILE_NAMES)
    def test_build(self, template_file_name):
        self.run_and_verify_no_crash("build", ["-t", os.path.join(TEMPLATE_FOLDER, template_file_name)])

    @parameterized.expand(TEMPLATE_FILE_NAMES)
    def test_validate(self, template_file_name):
        self.run_and_verify_no_crash("validate", ["-t", os.path.join(TEMPLATE_FOLDER, template_file_name)])

    @parameterized.expand(TEMPLATE_FILE_NAMES)
    def test_local_invoke(self, template_file_name):
        self.run_and_verify_no_crash("local invoke", ["-t", os.path.join(TEMPLATE_FOLDER, template_file_name)])

    @parameterized.expand(TEMPLATE_FILE_NAMES)
    def test_package(self, template_file_name):
        self.run_and_verify_no_crash(
            "package",
            [
                "--template-file",
                os.path.join(TEMPLATE_FOLDER, template_file_name),
                "--s3-bucket",
                "sdfafds-random-bucket",
            ],
        )

    @parameterized.expand(TEMPLATE_FILE_NAMES)
    def test_deploy(self, template_file_name):
        self.run_and_verify_no_crash(
            "deploy",
            [
                "--template-file",
                os.path.join(TEMPLATE_FOLDER, template_file_name),
                "--stack-name",
                "dsfafs-random-stack",
            ],
        )

    def run_and_verify_no_crash(self, cmd_name, args):
        sam_cmd = "samdev" if os.getenv("SAM_CLI_DEV", 0) else "sam"
        # if a previous smoke test run have been killed, re-running them will fail. so run them in a temp folder
        with tempfile.TemporaryDirectory() as temp:
            # Create isolated config directory for each test to prevent metadata.json conflicts
            env = os.environ.copy()
            # Use a unique subdirectory for SAM CLI config to avoid concurrent access issues
            config_dir = os.path.join(temp, ".aws-sam")
            env["__SAM_CLI_APP_DIR"] = config_dir

            process = subprocess.Popen(
                [sam_cmd, cmd_name] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=temp,
                env=env,  # Use modified environment with isolated config dir
            )
            stdout, stderr = process.communicate()

            # Just make sure "Traceback" is not in the stdout and stderr - aka the command didn't blow up with stacktrace
            self.assertNotIn("Traceback", str(stdout.decode("utf-8")))
            self.assertNotIn("Traceback", str(stderr.decode("utf-8")))
