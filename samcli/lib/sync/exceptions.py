"""Exceptions related to sync functionalities"""
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from samcli.lib.sync.sync_flow import SyncFlow


class SyncFlowException(Exception):
    """Exception wrapper for exceptions raised in SyncFlows"""

    _sync_flow: "SyncFlow"
    _exception: Exception

    def __init__(self, sync_flow: "SyncFlow", exception: Exception):
        """
        Parameters
        ----------
        sync_flow : SyncFlow
            SyncFlow that raised the exception
        exception : Exception
            exception raised
        """
        super().__init__(f"SyncFlow Exception for {sync_flow.log_name}")
        self._sync_flow = sync_flow
        self._exception = exception

    @property
    def sync_flow(self) -> "SyncFlow":
        return self._sync_flow

    @property
    def exception(self) -> Exception:
        return self._exception


class InfraSyncRequiredError(Exception):
    """Exception used if SyncFlow cannot handle the sync and an infra sync is required"""

    _resource_identifier: Optional[str]
    _reason: Optional[str]

    def __init__(self, resource_identifier: Optional[str] = None, reason: Optional[str] = ""):
        """
        Parameters
        ----------
        resource_identifier : str
            Logical resource identifier
        reason : str
            Reason for requiring infra sync
        """
        super().__init__(f"{resource_identifier} cannot be code synced.")
        self._resource_identifier = resource_identifier
        self._reason = reason

    @property
    def resource_identifier(self) -> Optional[str]:
        """
        Returns
        -------
        str
            Resource identifier of the resource that does not have a remote/physical counterpart
        """
        return self._resource_identifier

    @property
    def reason(self) -> Optional[str]:
        """
        Returns
        -------
        str
            Reason to why the SyncFlow cannot sync the resource
        """
        return self._reason


class MissingPhysicalResourceError(Exception):
    """Exception used for not having a remote/physical counterpart for a local stack resource"""

    _resource_identifier: Optional[str]
    _physical_resource_mapping: Optional[Dict[str, str]]

    def __init__(
        self, resource_identifier: Optional[str] = None, physical_resource_mapping: Optional[Dict[str, str]] = None
    ):
        """
        Parameters
        ----------
        resource_identifier : str
            Logical resource identifier
        physical_resource_mapping: Dict[str, str]
            Current mapping between logical and physical IDs
        """
        super().__init__(f"{resource_identifier} is not found in remote.")
        self._resource_identifier = resource_identifier
        self._physical_resource_mapping = physical_resource_mapping

    @property
    def resource_identifier(self) -> Optional[str]:
        """
        Returns
        -------
        str
            Resource identifier of the resource that does not have a remote/physical counterpart
        """
        return self._resource_identifier

    @property
    def physical_resource_mapping(self) -> Optional[Dict[str, str]]:
        """
        Returns
        -------
        Optional[Dict[str, str]]
            Physical ID mapping for resources when the excecption was raised
        """
        return self._physical_resource_mapping


class NoLayerVersionsFoundError(Exception):
    """This is used when we try to list all versions for layer, but we found none"""

    _layer_name_arn: str

    def __init__(self, layer_name_arn: str):
        """
        Parameters
        ----------
        layer_name_arn : str
            Layer ARN without version info at the end of it
        """
        super().__init__(f"{layer_name_arn} doesn't have any versions in remote.")
        self._layer_name_arn = layer_name_arn

    @property
    def layer_name_arn(self) -> str:
        """
        Returns
        -------
        str
            Layer ARN without version info at the end of it
        """
        return self._layer_name_arn


class MissingLockException(Exception):
    """Exception for not having an associated lock to be used."""


class MissingFunctionBuildDefinition(Exception):
    """This is used when no build definition found for particular function"""

    _function_logical_id: str

    def __init__(self, function_logical_id: str):
        super().__init__(f"Build definition for {function_logical_id} can't be found")
        self._function_logical_id = function_logical_id

    @property
    def function_logical_id(self) -> str:
        return self._function_logical_id


class InvalidRuntimeDefinitionForFunction(Exception):
    """This is used when no Runtime information is defined for a function resource"""

    _function_logical_id: str

    def __init__(self, function_logical_id):
        super().__init__(f"Invalid Runtime definition for {function_logical_id}")
        self._function_logical_id = function_logical_id

    @property
    def function_logical_id(self):
        return self._function_logical_id
