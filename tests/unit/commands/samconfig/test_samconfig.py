"""
Tests whether SAM Config is being read by all CLI commands
"""

import os
import shutil
import tempfile
from pathlib import Path
from contextlib import contextmanager
from samcli.lib.config.samconfig import SamConfig, DEFAULT_ENV

from click.testing import CliRunner

from unittest import TestCase
from mock import patch
import logging

LOG = logging.getLogger()
logging.basicConfig()

config = """
version = 0.1

[default.build.parameters]
profile="srirammv"
parameter_overrides="Stage=Prod Version=python3.7"
debug=true
skip_pull_image=true
use_container=true

[default.package.parameters]
profile="srirammv"
region="us-east-1"
s3_bucket="windowssam"
output_template_file="packaged.yaml"

[default.deploy.parameters]
parameter_overrides="Stage=Prod Version=python3.7"
stack_name="ennamo"
capabilities="CAPABILITY_IAM CAPABILITY_NAMED_IAM"
region="us-east-1"
profile="srirammv"
s3_bucket="sam-app-package"

[default.local_start_api.parameters]
port=5401

[default.local_generate_event_alexa_skills_kit_intent_answer.parameters]
session_id="from_config"
"""


class TestSamConfigForAllCommands(TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self.scratch_dir = tempfile.mkdtemp()
        os.chdir(self.scratch_dir)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.scratch_dir)
        self.scratch_dir = None

    def test_init(self):
        pass

    def test_validate(self):
        pass

    def test_build(self):
        pass

    def test_local_invoke(self):
        pass

    def test_local_generate_event(self):
        pass

    def test_local_start_api(self):
        pass

    def test_local_start_lambda(self):
        pass

    def test_package(self):
        pass

    @patch("samcli.commands.deploy.command.do_cli")
    def test_deploy(self, do_cli_mock):

        config_values = {
            "template_file": "mytemplate.yaml",
            "stack_name": "mystack",
            "s3_bucket": "mybucket",
            "force_upload": True,
            "s3_prefix": "myprefix",
            "kms_key_id": "mykms",
            "parameter_overrides": "ParameterKey=Key,ParameterValue=Value",
            "capabilities": "cap1 cap2",
            "no_execute_changeset": True,
            "role_arn": "arn",
            "notification_arns": "notify1 notify2",
            "fail_on_empty_changeset": True,
            "use_json": True,
            "tags": 'a=tag1 b="tag with spaces"',
            "metadata": '{"m1": "value1", "m2": "value2"}',
            "guided": True,
            "confirm_changeset": True,
            "region": "myregion",
        }

        with samconfig_parameters(["deploy"], self.scratch_dir, **config_values) as config_path:

            from samcli.commands.deploy.command import cli

            runner = CliRunner()
            result = runner.invoke(cli, [])

            LOG.info(result.output)
            LOG.info(result.exception)
            if result.exception:
                LOG.exception("Command failed", exc_info=result.exc_info)
            self.assertIsNone(result.exception)

            do_cli_mock.assert_called_with(
                str(Path(os.getcwd(), "mytemplate.yaml")),
                "mystack",
                "mybucket",
                True,
                "myprefix",
                "mykms",
                {"Key": "Value"},
                ["cap1", "cap2"],
                True,
                "arn",
                ["notify1", "notify2"],
                True,
                True,
                {"a": "tag1", "b": '"tag with spaces"'},
                {"m1": "value1", "m2": "value2"},
                True,
                True,
                "myregion",
                None,
            )

    def test_logs(self):
        pass

    def test_publish(self):
        pass


@contextmanager
def samconfig_parameters(cmd_names, config_dir=None, env=None, **kwargs):
    """
    ContextManager to write a new SAM Config and remove the file after the contextmanager exists

    Parameters
    ----------
    cmd_names : list(str)
        Name of the full commnad split as a list: ["generate-event", "s3", "put"]

    config_dir : str
        Path where the SAM config file should be written to. Defaults to os.getcwd()

    env : str
        Optional name of the config environment. This is currently unused

    kwargs : dict
        Parameter names and values to be written to the file.

    Returns
    -------
    Path to the config file
    """

    env = env or DEFAULT_ENV
    section = "parameters"
    samconfig = SamConfig(config_dir=config_dir)

    try:
        for k, v in kwargs.items():
            samconfig.put(cmd_names, section, k, v, env=env)

        samconfig.flush()
        yield samconfig.path()
    finally:
        Path(samconfig.path()).unlink()
