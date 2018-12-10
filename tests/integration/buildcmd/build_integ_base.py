import os
import shutil
import tempfile

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from unittest import TestCase


class BuildIntegBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()

        integration_dir = Path(__file__).resolve().parents[1]

        # To invoke a function creaated by the build command, we need the built artifacts to be in a
        # location that is shared in Docker. Most temp directories are not shared. Therefore we are
        # using a scratch space within the test folder that is .gitignored. Contents of this folder
        # is also deleted after every test run
        cls.scratch_dir = str(Path(__file__).resolve().parent.joinpath("scratch"))

        cls.test_data_path = str(Path(integration_dir, "testdata", "buildcmd"))
        cls.template_path = str(Path(cls.test_data_path, "template.yaml"))

    def setUp(self):

        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        os.mkdir(self.scratch_dir)

        self.working_dir = tempfile.mkdtemp(dir=self.scratch_dir)
        self.custom_build_dir = tempfile.mkdtemp(dir=self.scratch_dir)

        self.default_build_dir = Path(self.working_dir, ".aws-sam", "build")
        self.built_template = self.default_build_dir.joinpath("template.yaml")

    def tearDown(self):
        self.custom_build_dir and shutil.rmtree(self.custom_build_dir)
        self.working_dir and shutil.rmtree(self.working_dir)
        self.scratch_dir and shutil.rmtree(self.scratch_dir)

    @classmethod
    def base_command(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(self, build_dir=None, base_dir=None, manifest_path=None, use_container=None,
                         parameter_overrides=None):

        command_list = [self.cmd, "build", "-t", self.template_path]

        if parameter_overrides:
            command_list += ["--parameter-overrides", self._make_parameter_override_arg(parameter_overrides)]

        if build_dir:
            command_list += ["-b", build_dir]

        if base_dir:
            command_list += ["-s", base_dir]

        if manifest_path:
            command_list += ["-m", manifest_path]

        if use_container:
            command_list += ["--use-container"]

        return command_list

    def _make_parameter_override_arg(self, overrides):
        return " ".join([
            "ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()
        ])
