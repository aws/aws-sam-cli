"""
Custom Lambda Authorizer class definition
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import parse_qsl

from samcli.commands.local.lib.validators.identity_source_validator import IdentitySourceValidator
from samcli.local.apigw.authorizers.authorizer import Authorizer
from samcli.local.apigw.exceptions import InvalidSecurityDefinition
from samcli.local.apigw.route import Route


class IdentitySource(ABC):
    def __init__(self, identity_source: str):
        """
        Abstract class representing an identity source validator

        Paramters
        ---------
        identity_source: str
            The identity source without any prefix
        """
        self.identity_source = identity_source

    @abstractmethod
    def is_valid(self, **kwargs) -> bool:
        """
        Validates if the identity source is present
        """

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, IdentitySource)
            and self.identity_source == other.identity_source
            and self.__class__ == other.__class__
        )


class HeaderIdentitySource(IdentitySource):
    def is_valid(self, **kwargs) -> bool:
        """
        Validates if the header is present and not empty

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `headers`

        Returns
        -------
        bool
            True if the header is present and not empty
        """
        headers = kwargs.get("headers", {})

        return bool(headers.get(self.identity_source, None))


class QueryIdentitySource(IdentitySource):
    def is_valid(self, **kwargs) -> bool:
        """
        Validates if the query string is present and not empty

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `querystring`

        Returns
        -------
        bool
            True if the query string is present and not empty
        """
        query_string = kwargs.get("querystring", "")

        if not query_string:
            return False

        query_string_list: List[Tuple[str, str]] = parse_qsl(query_string)

        for key, value in query_string_list:
            if key == self.identity_source and value:
                return True

        return False


class ContextIdentitySource(IdentitySource):
    def is_valid(self, **kwargs) -> bool:
        """
        Validates if the context key is present and not empty

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `context`

        Returns
        -------
        bool
            True if the context key is present and not empty
        """
        context = kwargs.get("context", {})

        return context.get(self.identity_source, None) is not None


class StageVariableIdentitySource(IdentitySource):
    def is_valid(self, **kwargs) -> bool:
        """
        Validates if the stage variable key is present and not empty

        Parameters
        ----------
        kwargs
            Keyword arguments containing `stageVariables`

        Returns
        -------
        bool
            True if the stage variable key is present and not empty
        """
        stage_variables = kwargs.get("stageVariables", {})

        return stage_variables.get(self.identity_source, None) is not None


@dataclass
class LambdaAuthorizer(Authorizer):
    TOKEN = "token"
    REQUEST = "request"
    VALID_TYPES = [TOKEN, REQUEST]

    PAYLOAD_V1 = "1.0"
    PAYLOAD_V2 = "2.0"
    PAYLOAD_VERSIONS = [PAYLOAD_V1, PAYLOAD_V2]

    def __init__(
        self,
        authorizer_name: str,
        type: str,
        lambda_name: str,
        identity_sources: List[str],
        payload_version: str,
        validation_string: Optional[str] = None,
        use_simple_response: bool = False,
    ):
        """
        Creates a Lambda Authorizer class

        Parameters
        ----------
        authorizer_name: str
            The name of the Lambda Authorizer
        type: str
            The type of authorizer this is (token or request)
        lambda_name: str
            The name of the Lambda function this authorizer invokes
        identity_sources: List[str]
            A list of strings that this authorizer uses
        payload_version: str
            The payload format version (1.0 or 2.0)
        validation_string: Optional[str] = None
            The regular expression that can be used to validate headers
        use_simple_responses: bool = False
            Boolean representing whether to return a simple response or not
        """
        self.authorizer_name = authorizer_name
        self.lambda_name = lambda_name
        self.type = type
        self.validation_string = validation_string
        self.payload_version = payload_version
        self.use_simple_response = use_simple_response

        self._parse_identity_sources(identity_sources)

    def __eq__(self, other):
        return (
            isinstance(other, LambdaAuthorizer)
            and self.lambda_name == other.lambda_name
            and sorted(self._identity_sources_raw) == sorted(other._identity_sources_raw)
            and self.validation_string == other.validation_string
            and self.use_simple_response == other.use_simple_response
            and self.payload_version == other.payload_version
            and self.authorizer_name == other.authorizer_name
            and self.type == other.type
        )

    @property
    def identity_sources(self) -> List[IdentitySource]:
        """
        The list of identity source validation objects

        Returns
        -------
        List[IdentitySource]
            A list of concrete identity source validation objects
        """
        return self._identity_sources

    @identity_sources.setter
    def identity_sources(self, identity_sources: List[str]) -> None:
        """
        Parses and sets the identity source validation objects

        Parameters
        ----------
        identity_sources: List[str]
            A list of strings of identity sources
        """
        self._parse_identity_sources(identity_sources)

    def _parse_identity_sources(self, identity_sources: List[str]) -> None:
        """
        Helper function to create identity source validation objects

        Parameters
        ----------
        identity_sources: List[str]
            A list of identity sources to parse
        """

        # validate incoming identity sources first
        for source in identity_sources:
            is_valid = IdentitySourceValidator.validate_identity_source(
                source, Route.API
            ) or IdentitySourceValidator.validate_identity_source(source, Route.HTTP)

            if not is_valid:
                raise InvalidSecurityDefinition(
                    f"Invalid identity source '{source}' for Lambda authorizer '{self.authorizer_name}"
                )

        identity_source_type = {
            "method.request.header.": HeaderIdentitySource,
            "$request.header.": HeaderIdentitySource,
            "method.request.querystring.": QueryIdentitySource,
            "$request.querystring.": QueryIdentitySource,
            "context.": ContextIdentitySource,
            "$context.": ContextIdentitySource,
            "stageVariables.": StageVariableIdentitySource,
            "$stageVariables.": StageVariableIdentitySource,
        }

        self._identity_sources_raw = identity_sources
        self._identity_sources = []

        for identity_source in self._identity_sources_raw:
            for prefix, identity_source_object in identity_source_type.items():
                if identity_source.startswith(prefix):
                    # get the stuff after the prefix
                    # and create the corresponding identity source object
                    property = identity_source[len(prefix) :]

                    # NOTE (lucashuy):
                    # need to ignore the typing here so that mypy doesn't complain
                    # about instantiating an abstract class
                    #
                    # `identity_source_object` (which comes from `identity_source_type`)
                    # is always a concrete class
                    identity_source_validator = identity_source_object(identity_source=property)  # type: ignore

                    self._identity_sources.append(identity_source_validator)

                    break
