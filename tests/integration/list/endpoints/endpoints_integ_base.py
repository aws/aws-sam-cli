from tests.integration.list.list_integ_base import ListIntegBase


class EndpointsIntegBase(ListIntegBase):
    def get_endpoints_command_list(
        self, stack_name=None, output=None, region=None, profile=None, template_file=None, help=False
    ):
        command_list = [self.base_command(), "list", "endpoints"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]

        if output:
            command_list += ["--output", str(output)]

        if region:
            command_list += ["--region", str(region)]

        if profile:
            command_list += ["--profile", str(profile)]

        if template_file:
            command_list += ["--template-file", str(template_file)]

        if help:
            command_list += ["--help"]

        return command_list
