import re
from samcli.lib.utils.hash import str_checksum


class CompanionStack:
    _parent_stack_name: str
    _escaped_parent_stack_name: str
    _parent_stack_hash: str
    _stack_name: str

    def __init__(self, parent_stack_name: str) -> None:
        self._parent_stack_name = parent_stack_name
        self._escaped_parent_stack_name = re.sub(r"[^a-z0-9]", "", self._parent_stack_name.lower())
        self._parent_stack_hash = str_checksum(self._parent_stack_name)
        self._stack_name = self._parent_stack_name[:104] + "-" + self._parent_stack_hash[:8] + "-CompanionStack"

    @property
    def parent_stack_name(self) -> str:
        return self._parent_stack_name

    @property
    def escaped_parent_stack_name(self) -> str:
        return self._escaped_parent_stack_name

    @property
    def parent_stack_hash(self) -> str:
        return self._parent_stack_hash

    @property
    def stack_name(self) -> str:
        return self._stack_name


class ECRRepo:
    _function_logical_id: str
    _escaped_function_logical_id: str
    _function_md5: str
    _companion_stack: str
    _logical_id: str
    _physical_id: str
    _output_logical_id: str

    def __init__(
        self,
        companion_stack: CompanionStack = None,
        function_logical_id: str = None,
        logical_id: str = None,
        physical_id: str = None,
        output_logical_id: str = None,
    ):
        self._function_logical_id = function_logical_id
        self._escaped_function_logical_id = (
            re.sub(r"[^a-z0-9]", "", self._function_logical_id.lower())
            if self._function_logical_id is not None
            else None
        )
        self._function_md5 = str_checksum(function_logical_id) if self._function_logical_id is not None else None
        self._companion_stack = companion_stack

        self._logical_id = logical_id
        self._physical_id = physical_id
        self._output_logical_id = output_logical_id

    @property
    def logical_id(self) -> str:
        if self._logical_id is None:
            self._logical_id = self._function_logical_id[:52] + self._function_md5[:8] + "Repo"
        return self._logical_id

    @property
    def physical_id(self) -> str:
        if self._physical_id is None:
            self._physical_id = (
                self._companion_stack.escaped_parent_stack_name
                + self._companion_stack.parent_stack_hash[:8]
                + "/"
                + self._escaped_function_logical_id
                + self._function_md5[:8]
                + "repo"
            )
        return self._physical_id

    @property
    def output_logical_id(self) -> str:
        if self._output_logical_id is None:
            self._output_logical_id = self._function_logical_id[:52] + self._function_md5[:8] + "Out"

    def get_repo_uri(self, account_id, region):
        return f"{account_id}.dkr.ecr.{region}.amazonaws.com/{self.physical_id}"
