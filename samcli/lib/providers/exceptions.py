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


class InvalidTemplateFile(Exception):
    """Exception when template validation fails"""

    _template: str
    _stack_name: str

    def __init__(self, template: str, stack_name: str) -> None:
        """Exception when template validation fails

        Parameters
        ----------
        template : str
            Template location that failed to validate
        stack_name : str
            Stack name of the template
        """
        self._template = template
        self._stack_name = stack_name
        super().__init__(f"Template at {template} for stack {stack_name} failed to validate.")

    @property
    def template(self) -> str:
        return self._template

    @property
    def stack_name(self) -> str:
        return self._stack_name


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
