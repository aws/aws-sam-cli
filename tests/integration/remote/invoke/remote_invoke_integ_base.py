from unittest import TestCase
from pathlib import Path
from typing import Optional

from tests.testing_utils import get_sam_command


class RemoteInvokeIntegBase(TestCase):
    template: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        cls.cmd = get_sam_command()
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata")
        if cls.template:
            cls.template_path = str(cls.test_data_path.joinpath("remote_invoke", cls.template))
        cls.events_folder_path = cls.test_data_path.joinpath("remote_invoke", "events")

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def get_command_list(
        stack_name=None,
        resource_id=None,
        event=None,
        event_file=None,
        parameter_list=None,
        output_format=None,
        region=None,
        profile=None,
        beta_features=None,
    ):
        command_list = [get_sam_command(), "remote", "invoke"]

        if stack_name:
            command_list = command_list + ["--stack-name", stack_name]

        if event:
            command_list = command_list + ["-e", event]

        if event_file:
            command_list = command_list + ["--event-file", event_file]

        if profile:
            command_list = command_list + ["--parameter", parameter]

        if output_format:
            command_list = command_list + ["--output-format", output_format]

        if parameter_list:
            for (parameter, value) in parameter_list:
                command_list = command_list + ["--parameter", f"{parameter}={value}"]

        if region:
            command_list = command_list + ["--region", region]

        if beta_features is not None:
            command_list = command_list + ["--beta-features" if beta_features else "--no-beta-features"]

        if resource_id:
            command_list = command_list + [resource_id]

        return command_list
