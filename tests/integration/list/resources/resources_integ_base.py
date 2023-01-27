from tests.integration.list.list_integ_base import ListIntegBase


class ResourcesIntegBase(ListIntegBase):
    def get_resources_command_list(
        self, stack_name=None, output=None, region=None, profile=None, template_file=None, help=False
    ):
        command_list = [self.base_command(), "list", "resources"]
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

    def assert_resource(self, resources, logical_id, physical_id):
        resource = self._find_resource(resources, logical_id)
        if not resource:
            raise AssertionError(f"Couldn't find resource with corresponding logical id {logical_id}")
        self.assertRegex(resource.get("PhysicalResourceId", ""), physical_id)
