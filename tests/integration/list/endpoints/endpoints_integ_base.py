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

    def assert_endpoints(self, endpoints, logical_id, physical_id, cloud_endpoints, methods):
        resource = self._find_resource(endpoints, logical_id)
        if not resource:
            raise AssertionError(f"Couldn't find endpoint with corresponding logical id {logical_id}")
        self.assertRegex(resource.get("PhysicalResourceId", ""), physical_id)
        self.assertEqual(resource.get("Methods", []), methods)
        self._assert_cloud_endpoints(resource, cloud_endpoints)

    def _assert_cloud_endpoints(self, resource, cloud_endpoints):
        deployed_endpoint = resource.get("CloudEndpoint")
        if isinstance(cloud_endpoints, str):
            self.assertRegex(deployed_endpoint, cloud_endpoints)
            return
        for deployed, expected in zip(deployed_endpoint, cloud_endpoints):
            self.assertRegex(deployed, expected)
