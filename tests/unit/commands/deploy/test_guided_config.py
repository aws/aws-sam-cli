import os
from unittest import TestCase
from unittest.mock import patch

import click

# TODO: importing private module property, to investigate alternative for stability
from click.globals import _local  # type: ignore
from click import Context

from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.lib.config.samconfig import SamConfig, DEFAULT_CONFIG_FILE_NAME
from samcli.lib.utils.osutils import tempfile_platform_independent, remove
from samcli.commands.deploy.guided_config import GuidedConfig


class TestGuidedConfig(TestCase):
    def setUp(self):
        setattr(
            _local,
            "stack",
            [
                Context(
                    command="test", allow_extra_args=False, allow_interspersed_args=False, ignore_unknown_options=False
                )
            ],
        )
        with tempfile_platform_independent() as template:
            self.template_file = os.path.abspath(template.name)
            self.samconfig_dir = os.path.dirname(self.template_file)
            self.samconfig_path = os.path.join(self.samconfig_dir, DEFAULT_CONFIG_FILE_NAME)
        self.gc = GuidedConfig(template_file=self.template_file, section="dummy")

    def tearDown(self):
        delattr(_local, "stack")
        remove(self.samconfig_path)

    def test_guided_config_init(self):
        ctx, samconfig = self.gc.get_config_ctx()
        self.assertTrue(isinstance(ctx, click.Context))
        self.assertTrue(isinstance(samconfig, SamConfig))

    def test_read_config_showcase(self):
        # No samconfig file present, no errors thrown.
        self.gc.read_config_showcase()
        with open(self.samconfig_path, "wb") as f:
            f.write(b"default\\n")
        # Empty samconfig, config file found but invalid
        with self.assertRaises(GuidedDeployFailedError):
            self.gc.read_config_showcase()

    @patch("samcli.commands.deploy.guided_config.get_cmd_names")
    def test_save_config(self, patched_cmd_names):
        patched_cmd_names.return_value = ["local", "start-api"]
        # Should save with no errors.
        signing_profiles = {
            "a": {"profile_name": "profile", "profile_owner": "owner"},
            "b": {"profile_name": "profile"},
        }
        self.gc.save_config(parameter_overrides={"a": "b"}, signing_profiles=signing_profiles, port="9090")

    @patch("samcli.commands.deploy.guided_config.get_cmd_names")
    def test_save_config_image_repositories(self, patched_cmd_names):
        patched_cmd_names.return_value = ["deploy"]
        # Should save with no errors.
        image_repositories = {"HelloWorldFunction": "sample-repo"}
        self.gc.save_config(parameter_overrides={"a": "b"}, image_repositories=image_repositories)
