"""
Custom Lambda Authorizer class definition
"""
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl

from samcli.commands.local.lib.validators.identity_source_validator import IdentitySourceValidator
from samcli.local.apigw.authorizers.authorizer import Authorizer
from samcli.local.apigw.exceptions import InvalidLambdaAuthorizerResponse, InvalidSecurityDefinition
from samcli.local.apigw.route import Route

_RESPONSE_PRINCIPAL_ID = "principalId"
_RESPONSE_CONTEXT = "context"
_RESPONSE_POLICY_DOCUMENT = "policyDocument"
_RESPONSE_IAM_STATEMENT = "Statement"
_RESPONSE_IAM_EFFECT = "Effect"
_RESPONSE_IAM_ACTION = "Action"
_RESPONSE_IAM_RESOURCE = "Resource"
_SIMPLE_RESPONSE_IS_AUTH = "isAuthorized"
_IAM_INVOKE_ACTION = "execute-api:Invoke"


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

    def is_valid(self, **kwargs) -> bool:
        """
        Validates if the identity source is present

        Parameters
        ----------
        kwargs: dict
            Key word arguments to search in

        Returns
        -------
        bool:
            True if the identity source is present
        """
        return self.find_identity_value(**kwargs) is not None

    @abstractmethod
    def find_identity_value(self, **kwargs) -> Any:
        """
        Returns the identity value, if found
        """

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, IdentitySource)
            and self.identity_source == other.identity_source
            and self.__class__ == other.__class__
        )


class HeaderIdentitySource(IdentitySource):
    def find_identity_value(self, **kwargs) -> Optional[str]:
        """
        Finds the header value that the identity source corresponds to

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `headers`

        Returns
        -------
        Optional[str]
            The string value of the header if it is found, otherwise None
        """
        headers = kwargs.get("headers", {})
        value = headers.get(self.identity_source)

        return str(value) if value else None


class QueryIdentitySource(IdentitySource):
    def find_identity_value(self, **kwargs) -> Optional[str]:
        """
        Finds the query string value that the identity source corresponds to

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `querystring`

        Returns
        -------
        Optional[str]
            The string value of the query parameter if one is found, otherwise None
        """
        query_string = kwargs.get("querystring", "")

        if not query_string:
            return None

        query_string_list: List[Tuple[str, str]] = parse_qsl(query_string)

        for key, value in query_string_list:
            if key == self.identity_source and value:
                return value

        return None


class ContextIdentitySource(IdentitySource):
    def find_identity_value(self, **kwargs) -> Optional[str]:
        """
        Finds the context value that the identity source corresponds to

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `context`

        Returns
        -------
        Optional[str]
            The string value of the context variable if it is found, otherwise None
        """
        context = kwargs.get("context", {})
        value = context.get(self.identity_source)

        return str(value) if value else None


class StageVariableIdentitySource(IdentitySource):
    def find_identity_value(self, **kwargs) -> Optional[str]:
        """
        Finds the stage variable value that the identity source corresponds to

        Parameters
        ----------
        kwargs
            Keyword arguments that should contain `stageVariables`

        Returns
        -------
        Optional[str]
            The stage variable if it is found, otherwise None
        """
        stage_variables = kwargs.get("stageVariables", {})
        value = stage_variables.get(self.identity_source)

        return str(value) if value else None


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

    def is_valid_response(self, response: str, method_arn: str) -> bool:
        """
        Validates whether a Lambda authorizer request is authenticated or not.

        Parameters
        ----------
        response: str
            JSON string containing the output from a Lambda authorizer

        Returns
        -------
        bool
            True if the request is properly authenticated
        """
        try:
            json_response = json.loads(response)
        except ValueError:
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer {self.authorizer_name} return an invalid response payload"
            )

        if self.payload_version == LambdaAuthorizer.PAYLOAD_V2 and self.use_simple_response:
            return self._validate_simple_response(json_response)

        return self._validate_iam_response(json_response, method_arn)

    def _validate_iam_response(self, response: dict, method_arn: str) -> bool:
        """
        Helper method to validate if a Lambda authorizer response is valid and authorized

        Parameters
        ----------
        response: dict
            JSON object from Lambda authorizer output
        method_arn: str
            The method ARN of this request

        Returns
        -------
        bool
            True if the request is authorized
        """
        # validate there exists a principalId (unique ID representing the authenticated request)
        if not response.get(_RESPONSE_PRINCIPAL_ID):
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer {self.authorizer_name} is missing {_RESPONSE_PRINCIPAL_ID} from response"
            )

        # validate there exists a policy document
        policy_document = response.get(_RESPONSE_POLICY_DOCUMENT)
        if not policy_document or not isinstance(policy_document, dict):
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer {self.authorizer_name} is missing {_RESPONSE_POLICY_DOCUMENT} from response"
            )

        # validate there is a statement property and that there is at least one
        all_statements = policy_document.get(_RESPONSE_IAM_STATEMENT)
        if not all_statements or not isinstance(all_statements, list) or not len(all_statements) > 0:
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer {self.authorizer_name} contains an invalid " f"or missing {_RESPONSE_IAM_STATEMENT}"
            )

        for statement in all_statements:
            # validate statement is an object
            if not statement or not isinstance(statement, dict):
                raise InvalidLambdaAuthorizerResponse(
                    f"Authorizer {self.authorizer_name} contains an invalid {_RESPONSE_IAM_STATEMENT}, "
                    "it must be an object"
                )

            # validate statement contains an action
            action = statement.get(_RESPONSE_IAM_ACTION)
            if not action:
                raise InvalidLambdaAuthorizerResponse(
                    f"Authorizer {self.authorizer_name} is missing {_RESPONSE_IAM_ACTION} from response"
                )

            # ignore action if it is not invoke
            if action != _IAM_INVOKE_ACTION:
                continue

            # validate statement contains effect
            effect = statement.get(_RESPONSE_IAM_EFFECT)
            if not effect:
                raise InvalidLambdaAuthorizerResponse(
                    f"Authorizer {self.authorizer_name} is missing {_RESPONSE_IAM_EFFECT} from response"
                )

            # ignore if the effect is not allow
            if effect != "Allow":
                continue

            # validate the method ARN is the one we are invoking
            all_resource_arns = statement.get(_RESPONSE_IAM_RESOURCE)
            if not all_resource_arns or not isinstance(all_resource_arns, list):
                raise InvalidLambdaAuthorizerResponse(
                    f"Authorizer {self.authorizer_name} is missing {_RESPONSE_IAM_RESOURCE} or "
                    f"{_RESPONSE_IAM_RESOURCE} is not a list"
                )

            for resource_arn in all_resource_arns:
                # form a regular expression from the possible wildcard resource ARN
                regex_method_arn = resource_arn.replace("*", ".+").replace("?", ".")
                regex_method_arn += "$"

                if re.match(regex_method_arn, method_arn):
                    return True

        return False

    def _validate_simple_response(self, response: dict) -> bool:
        """
        Helper method to validate if a Lambda authorizer response using simple responses is valid and authorized

        Parameters
        ----------
        response: dict
            JSON object containing required simple response paramters

        Returns
        -------
        bool
            True if the request is authorized
        """
        is_authorized = response.get(_SIMPLE_RESPONSE_IS_AUTH)

        if is_authorized is None or not isinstance(is_authorized, bool):
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer {self.authorizer_name} is missing or contains an invalid " f"{_SIMPLE_RESPONSE_IS_AUTH}"
            )

        return is_authorized

    @staticmethod
    def get_context(response: dict) -> Dict[str, Any]:
        """
        Returns the context (if set) from the authorizer response and appends the principalId to it.

        Parameters
        ----------
        response: dict
            JSON object output from Lambda Authorizer

        Returns
        -------
        Dict[str, Any]
            The built authorizer context object
        """
        built_context = response.get(_RESPONSE_CONTEXT, {})
        built_context[_RESPONSE_PRINCIPAL_ID] = response.get(_RESPONSE_PRINCIPAL_ID)

        return built_context  # type: ignore
