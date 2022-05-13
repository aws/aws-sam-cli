from typing import List

from samcli.lib.providers.provider import ResourceIdentifier, get_full_path, Stack
from samcli.lib.utils.cloudformation import get_resource_summaries, CloudFormationResourceSummary


class RemoteStack:

    def __init__(self, stack_name, stack, stacks, logical_id="", provider=None):
        self._provider = provider
        self._logical_stack_name = logical_id
        self._local_stack = stack
        self._stacks = stacks
        self._stack_name = stack_name
        self._resources: List[CloudFormationResourceSummary] = []
        self._children = []

    def get_remote_info(self, resource_id_mapping):
        resources_summaries = get_resource_summaries(
            self._provider,
            self._stack_name
        )

        for resource_summary in resources_summaries:
            if resource_summary.resource_type == "AWS::CloudFormation::Stack":
                child_stack_name = resource_summary.physical_resource_id.split("/")[1]
                local_child_stacks = Stack.get_child_stacks(self._local_stack, self._stacks)
                child_local_stack = Stack.get_stack_by_logical(resource_summary.logical_resource_id, local_child_stacks)
                self._children.append(
                    RemoteStack(child_stack_name, child_local_stack, self._stacks, resource_summary.logical_resource_id, self._provider))
            else:
                self._resources.append(resource_summary)
                resource_id = get_full_path(self._local_stack.stack_path, resource_summary.logical_resource_id)
                resource_id_mapping[resource_id] = resource_summary.physical_resource_id

        for child in self._children:
            child.get_remote_info(resource_id_mapping)

        return resource_id_mapping

