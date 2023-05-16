import pytest
from unittest import TestCase

from tests.testing_utils import get_sam_command


@pytest.mark.xdist_group(name="sam_init")
class InitIntegBase(TestCase):
    BINARY_READY_WAIT_TIME = 5

    def get_command(
        self,
        runtime=None,
        dependency_manager=None,
        architecture=None,
        app_template=None,
        name=None,
        no_interactive=None,
        output=None,
    ):
        command_list = [get_sam_command(), "init"]

        if runtime:
            command_list += ["--runtime", runtime]

        if dependency_manager:
            command_list += ["--dependency-manager", dependency_manager]

        if architecture:
            command_list += ["--architecture", architecture]

        if app_template:
            command_list += ["--app-template", app_template]

        if name:
            command_list += ["--name", name]

        if no_interactive:
            command_list += ["--no-interactive"]

        if output:
            command_list += ["-o", output]

        return command_list
