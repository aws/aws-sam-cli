"""
Exceptions used by providers
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:  # pragma: no cover
    from samcli.lib.providers.provider import ResourceIdentifier


class InvalidLayerReference(Exception):
    """
    Raised when the LayerVersion LogicalId does not exist in the template
    """

    def __init__(self) -> None:
        super().__init__(
            "Layer References need to be of type " "'AWS::Serverless::LayerVersion' or 'AWS::Lambda::LayerVersion'"
        )


class RemoteStackLocationNotSupported(Exception):
    pass


class MissingCodeUri(Exception):
    """Exception when Function or Lambda resources do not have CodeUri specified"""


class MissingLocalDefinition(Exception):
    """Exception when a resource does not have local path in it's property"""

    _resource_identifier: "ResourceIdentifier"
    _property_name: str

    def __init__(self, resource_identifier: "ResourceIdentifier", property_name: str) -> None:
        """Exception when a resource does not have local path in it's property

        Parameters
        ----------
        resource_identifier : ResourceIdentifier
            Resource Identifer
        property_name : str
            Property name that's missing
        """
        self._resource_identifier = resource_identifier
        self._property_name = property_name
        super().__init__(f"Resource {str(resource_identifier)} does not have {property_name} specified.")

    @property
    def resource_identifier(self) -> "ResourceIdentifier":
        return self._resource_identifier

    @property
    def property_name(self) -> str:
        return self._property_name
