from tests.integration.list.list_integ_base import ListIntegBase


class StackOutputsIntegBase(ListIntegBase):
    def get_stack_outputs_command_list(self, stack_name=None, output=None, region=None, profile=None, help=False):
        command_list = [self.base_command(), "list", "stack-outputs"]
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
