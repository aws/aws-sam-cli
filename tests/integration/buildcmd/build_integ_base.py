import os
import shutil
import tempfile
import logging
import subprocess
import json
from unittest import TestCase

import docker

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

from samcli.yamlhelper import yaml_parse


LOG = logging.getLogger(__name__)


class BuildIntegBase(TestCase):
    template = "template.yaml"

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
        cls.template_path = str(Path(cls.test_data_path, cls.template))

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

    def get_command_list(
        self,
        build_dir=None,
        base_dir=None,
        manifest_path=None,
        use_container=None,
        parameter_overrides=None,
        mode=None,
        function_identifier=None,
    ):

        command_list = [self.cmd, "build"]

        if function_identifier:
            command_list += [function_identifier]

        command_list += ["-t", self.template_path]

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

    def verify_docker_container_cleanedup(self, runtime):
        docker_client = docker.from_env()
        samcli_containers = docker_client.containers.list(
            all=True, filters={"ancestor": "lambci/lambda:build-{}".format(runtime)}
        )
        self.assertFalse(bool(samcli_containers), "Build containers have not been removed")

    def _make_parameter_override_arg(self, overrides):
        return " ".join(["ParameterKey={},ParameterValue={}".format(key, value) for key, value in overrides.items()])

    def _verify_resource_property(self, template_path, logical_id, property, expected_value):

        with open(template_path, "r") as fp:
            template_dict = yaml_parse(fp.read())
            self.assertEquals(expected_value, template_dict["Resources"][logical_id]["Properties"][property])

    def _verify_invoke_built_function(self, template_path, function_logical_id, overrides, expected_result):
        LOG.info("Invoking built function '{}'".format(function_logical_id))

        cmdlist = [
            self.cmd,
            "local",
            "invoke",
            function_logical_id,
            "-t",
            str(template_path),
            "--no-event",
            "--parameter-overrides",
            overrides,
        ]

        process = subprocess.Popen(cmdlist, stdout=subprocess.PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()).strip().decode("utf-8")
        self.assertEquals(json.loads(process_stdout), expected_result)
