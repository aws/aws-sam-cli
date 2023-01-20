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

    def check_stack_output(self, output, key=None, value=None, description=None):
        if key:
            self._check_key(output, key)
        if value:
            self._check_value(output, value)
        if description:
            self._check_description(output, description)

    def _check_key(self, output, key):
        output_key = output.get("OutputKey")
        self.assertEqual(output_key, key)

    def _check_value(self, output, value):
        output_value = output.get("OutputValue")
        self.assertRegex(output_value, value)

    def _check_description(self, output, description):
        output_description = output.get("Description")
        self.assertEqual(output_description, description)
