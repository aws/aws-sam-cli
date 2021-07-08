"""Exceptions related to sync functionalities"""
from typing import List


class MissingPhysicalResourceError(Exception):
    """Exception used for not having a remote/physical counterpart for a local stack resource"""

    _resource_identifier: str

    def __init__(self, resource_identifier: str):
        """
        Parameters
        ----------
        resource_identifier : str
            Logical resource identifier
        """
        super().__init__(f"{resource_identifier} is not found in remote.")
        self._resource_identifier = resource_identifier

    @property
    def resource_identifier(self) -> str:
        """
        Returns
        -------
        str
            Resource identifier of the resource that does not have a remote/physical counterpart
        """
        return self._resource_identifier


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


class LayerPhysicalIdNotFoundError(Exception):
    """This is used when we can't find physical id of a given layer resource"""

    _layer_name: str
    _stack_resource_names: List[str]

    def __init__(self, layer_name: str, stack_resource_names: List[str]):
        super().__init__(f"Can't find {layer_name} in stack resources {stack_resource_names}")
        self._layer_name = layer_name
        self._stack_resource_names = stack_resource_names

    @property
    def layer_name(self) -> str:
        """
        Returns
        -------
        str
            Layer name as it is written in template file
        """
        return self._layer_name

    @property
    def stack_resource_names(self) -> List[str]:
        """
        Returns
        -------
        List[str]
            List of resource names that is actually deployed into CFN stack
        """
        return self._stack_resource_names


class MissingLockException(Exception):
    """Exception for not having an associated lock to be used."""


class UriNotFoundException(Exception):
    """Exception used for not having a URI field that the resource requires"""

    _resource_identifier: str
    _property_name: str

    def __init__(self, resource_identifier: str, property_name: str):
        """
        Parameters
        ----------
        resource_identifier : str
            Logical resource identifier
        property_name: str
            Property name related to the URI
        """
        super().__init__(f"{resource_identifier} doesn't contain the {property_name} field which is required.")
        self._resource_identifier = resource_identifier
        self._property_name = property_name

    @property
    def resource_identifier(self) -> str:
        """
        Returns
        -------
        str
            Resource identifier of the resource that does not have a remote/physical counterpart
        """
        return self._resource_identifier

    @property
    def property_name(self) -> str:
        """
        Returns
        -------
        str
            Property name related to the URI property required
        """
        return self._property_name
