from typing import List

from samcli.lib.utils.cloudformation import get_resource_summaries, CloudFormationResourceSummary


class RemoteStack:

    def __init__(self, stack_name, logical_id="", provider=None, path=""):
        self._provider = provider
        self._logical_stack_name = logical_id
        self._stack_name = stack_name
        self._resources: List[CloudFormationResourceSummary] = []
        self._children = []
        self._path = path + "/" if path else ""
        self._path = self._path + self._logical_stack_name + "/" if self._logical_stack_name else ""

    def get_remote_info(self, resource_id_mapping):
        resources_summaries = get_resource_summaries(
            self._provider,
            self._stack_name
        )

        for resource_summary in resources_summaries:
            if resource_summary.resource_type == "AWS::CloudFormation::Stack":
                child_stack_name = resource_summary.physical_resource_id.split("/")[1]
                self._children.append(
                    RemoteStack(child_stack_name, resource_summary.logical_resource_id, self._provider, self._path))
            else:
                self._resources.append(resource_summary)
                resource_id_mapping[
                    self._path + resource_summary.logical_resource_id] = resource_summary.physical_resource_id

        for child in self._children:
            child.get_remote_info(resource_id_mapping)

        return resource_id_mapping
