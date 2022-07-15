from tests.integration.list.list_integ_base import ListIntegBase


class TestableResourcesIntegBase(ListIntegBase):
    def get_testable_resources_command_list(self, stack_name=None, output=None, region=None, profile=None, help=False):
        command_list = [self.base_command(), "list", "testable-resources"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]

        if output:
            command_list += ["--output", str(output)]

        if region:
            command_list += ["--region", str(region)]

        if profile:
            command_list += ["--profile", str(profile)]

        if help:
            command_list += ["--help"]

        return command_list
