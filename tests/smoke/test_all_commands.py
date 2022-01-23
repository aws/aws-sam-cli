import os
import subprocess
import tempfile

from parameterized import parameterized
from unittest import TestCase


TEMPLATE_FOLDER = os.path.join(os.path.dirname(__file__), "templates", "sar")
TEMPLATE_FILE_NAMES = [v for v in os.listdir(TEMPLATE_FOLDER) if "yaml" in v]


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
            process = subprocess.Popen(
                [sam_cmd, cmd_name] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=temp
            )
            stdout, stderr = process.communicate()

            # Just make sure "Traceback" is not in the stdout and stderr - aka the command didn't blow up with stacktrace
            self.assertNotIn("Traceback", str(stdout.decode("utf-8")))
            self.assertNotIn("Traceback", str(stderr.decode("utf-8")))
