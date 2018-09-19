import os
from unittest import TestCase

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class InvokeIntegBase(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()

        integration_dir = str(Path(__file__).resolve().parents[2])

        cls.test_data_path = os.path.join(integration_dir, "testdata")
        cls.template_path = os.path.join(cls.test_data_path, "invoke", "template.yml")
        cls.event_path = os.path.join(cls.test_data_path, "invoke", "event.json")
        cls.env_var_path = os.path.join(cls.test_data_path, "invoke", "vars.json")

    @classmethod
    def base_command(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(self, function_to_invoke, template_path=None, event_path=None, env_var_path=None,
                         parameter_overrides=None, region=None):
        command_list = [self.cmd, "local", "invoke", function_to_invoke]

        if template_path:
            command_list = command_list + ["-t", template_path]

        if event_path:
            command_list = command_list + ["-e", event_path]

        if env_var_path:
            command_list = command_list + ["-n", env_var_path]

        if parameter_overrides:
            arg_value = " ".join([
                "ParameterKey={},ParameterValue={}".format(key, value) for key, value in parameter_overrides.items()
            ])
            command_list = command_list + ["--parameter-overrides", arg_value]

        if region:
            command_list = command_list + ["--region", region]

        return command_list
