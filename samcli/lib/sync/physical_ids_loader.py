from samcli.lib.sync.remote_stack import RemoteStack


class PhysicalIdsLoader:

    def __init__(self, root_stack_name, provider, stacks):
        self._root_stack_name = root_stack_name
        self._resource_id_to_physical_id = {}
        self._provider = provider
        self._stacks = stacks
        self._root_stack = self.get_root_stack()

    def load(self):
        root_stack = RemoteStack(stack_name=self._root_stack_name, stack=self._root_stack, stacks=self._stacks, logical_id="", provider=self._provider)
        root_stack.get_remote_info(self._resource_id_to_physical_id)
        return self._resource_id_to_physical_id

    def get_physical_id_by_resource_id(self, resource_id):
        return self._resource_id_to_physical_id.get(resource_id, "")

    def get_root_stack(self):
        for stack in self._stacks:
            if stack.is_root_stack:
                return  stack
