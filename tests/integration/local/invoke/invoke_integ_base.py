import os
from unittest import TestCase
from pathlib import Path


class InvokeIntegBase(TestCase):
    template = None

    @classmethod
    def setUpClass(cls):
        cls.cmd = cls.base_command()
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata")
        cls.template_path = str(cls.test_data_path.joinpath("invoke", cls.template))
        cls.event_path = str(cls.test_data_path.joinpath("invoke", "event.json"))
        cls.env_var_path = str(cls.test_data_path.joinpath("invoke", "vars.json"))
        cls.base_dir = "base_dir"

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @classmethod
    def base_command(cls):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(
        self,
        function_to_invoke,
        template_path=None,
        event_path=None,
        env_var_path=None,
        parameter_overrides=None,
        region=None,
        no_event=None,
        profile=None,
        layer_cache=None,
        docker_network=None,
        base_dir=None,
    ):
        command_list = [self.cmd, "local", "invoke", function_to_invoke]

        if template_path:
            command_list = command_list + ["-t", template_path]

        if event_path:
            command_list = command_list + ["-e", event_path]

        if env_var_path:
            command_list = command_list + ["-n", env_var_path]

        if no_event:
            command_list = command_list + ["--no-event"]

        if profile:
            command_list = command_list + ["--profile", profile]

        if layer_cache:
            command_list = command_list + ["--layer-cache-basedir", layer_cache]

        if docker_network:
            command_list = command_list + ["--docker-network", docker_network]

        if parameter_overrides:
            arg_value = " ".join(
                ["ParameterKey={},ParameterValue={}".format(key, value) for key, value in parameter_overrides.items()]
            )
            command_list = command_list + ["--parameter-overrides", arg_value]

        if region:
            command_list = command_list + ["--region", region]

        if base_dir:
            command_list = command_list + ["--base-dir", base_dir]

        return command_list
