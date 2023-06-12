"""
Custom Lambda Authorizer class definition
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from json import JSONDecodeError, loads
from typing import Any, Dict, List, Optional, Tuple, Type
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
_RESPONSE_IAM_EFFECT_ALLOW = "Allow"
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

    def is_valid(self, **kwargs) -> bool:
        """
        Validates whether the required header is present and matches the
        validation expression, if defined.

        Parameters
        ----------
        kwargs: dict
            Keyword arugments containing the incoming sources and validation expression

        Returns
        -------
        bool
            True if present and valid
        """
        identity_source = self.find_identity_value(**kwargs)
        validation_expression = kwargs.get("validation_expression")

        if validation_expression and identity_source is not None:
            return re.match(validation_expression, identity_source) is not None

        return identity_source is not None


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
        method_arn: str
            The method ARN of the route that invoked the Lambda authorizer

        Returns
        -------
        bool
            True if the request is properly authenticated
        """
        try:
            json_response = loads(response)
        except (ValueError, JSONDecodeError):
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer {self.authorizer_name} return an invalid response payload"
            )

        if self.payload_version == LambdaAuthorizer.PAYLOAD_V2 and self.use_simple_response:
            return self._validate_simple_response(json_response)

        # validate IAM policy document
        LambdaAuthorizerIAMPolicyValidator.validate_policy_document(self.authorizer_name, json_response)
        LambdaAuthorizerIAMPolicyValidator.validate_statement(self.authorizer_name, json_response)

        return self._is_resource_authorized(json_response, method_arn)

    def _is_resource_authorized(self, response: dict, method_arn: str) -> bool:
        """
        Validate the if the current method ARN is actually authorized

        Parameters
        ----------
        response: dict
            The response output from the Lambda authorizer (should be in IAM format)
        method_arn: str
            The route's method ARN

        Returns
        -------
        bool
            True if authorized
        """
        policy_document = response.get(_RESPONSE_POLICY_DOCUMENT, {})
        all_statements = policy_document.get(_RESPONSE_IAM_STATEMENT, [])

        for statement in all_statements:
            if statement.get(_RESPONSE_IAM_EFFECT) != _RESPONSE_IAM_EFFECT_ALLOW:
                continue

            action = statement.get(_RESPONSE_IAM_ACTION, [])
            action_list = action if isinstance(action, list) else [action]

            if _IAM_INVOKE_ACTION not in action_list:
                continue

            resource = statement.get(_RESPONSE_IAM_RESOURCE, [])
            resource_list = resource if isinstance(resource, list) else [resource]

            for resource_arn in resource_list:
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

    def get_context(self, response: str) -> Dict[str, Any]:
        """
        Returns the context (if set) from the authorizer response and appends the principalId to it.

        Parameters
        ----------
        response: str
            Output from Lambda authorizer

        Returns
        -------
        Dict[str, Any]
            The built authorizer context object
        """
        invalid_message = f"Authorizer {self.authorizer_name} return an invalid response payload"

        try:
            json_response = loads(response)
        except (ValueError, JSONDecodeError) as ex:
            raise InvalidLambdaAuthorizerResponse(invalid_message) from ex

        if not isinstance(json_response, dict):
            raise InvalidLambdaAuthorizerResponse(invalid_message)

        built_context = json_response.get(_RESPONSE_CONTEXT, {})

        if not isinstance(built_context, dict):
            raise InvalidLambdaAuthorizerResponse(invalid_message)

        principal_id = json_response.get(_RESPONSE_PRINCIPAL_ID)
        if principal_id:
            # only V1 response contains this ID in the output
            built_context[_RESPONSE_PRINCIPAL_ID] = principal_id

        return built_context


@dataclass
class LambdaAuthorizerIAMPolicyPropertyValidator:
    property_key: str
    property_types: List[Type]

    def is_valid(self, response: dict) -> bool:
        """
        Validates whether the property is present and of the correct type

        Parameters
        ----------
        response: dict
            The response output from the Lambda authorizer (should be in IAM format)

        Returns
        -------
        bool
            True if present and of correct type
        """
        value = response.get(self.property_key)

        if value is None:
            return False

        for property_type in self.property_types:
            if isinstance(value, property_type):
                return True

        return False


class LambdaAuthorizerIAMPolicyValidator:
    @staticmethod
    def validate_policy_document(auth_name: str, response: dict) -> None:
        """
        Validate the properties of a Lambda authorizer response at the root level

        Parameters
        ----------
        auth_name: str
            Name of the authorizer
        response: dict
            The response output from the Lambda authorizer (should be in IAM format)
        """
        validators = {
            _RESPONSE_PRINCIPAL_ID: LambdaAuthorizerIAMPolicyPropertyValidator(_RESPONSE_PRINCIPAL_ID, [str]),
            _RESPONSE_POLICY_DOCUMENT: LambdaAuthorizerIAMPolicyPropertyValidator(_RESPONSE_POLICY_DOCUMENT, [dict]),
        }

        for prop_name, validator in validators.items():
            if not validator.is_valid(response):
                raise InvalidLambdaAuthorizerResponse(
                    f"Authorizer '{auth_name}' contains an invalid or " f"missing '{prop_name}' from response"
                )

    @staticmethod
    def validate_statement(auth_name: str, response: dict) -> None:
        """
        Validate the Statement(s) of a Lambda authorizer response's policy document

        Parameters
        ----------
        auth_name: str
            Name of the authorizer
        response: dict
            The response output from the Lambda authorizer (should be in IAM format)
        """
        policy_document = response.get(_RESPONSE_POLICY_DOCUMENT, {})

        all_statements = policy_document.get(_RESPONSE_IAM_STATEMENT)
        if not all_statements or not isinstance(all_statements, list) or not len(all_statements) > 0:
            raise InvalidLambdaAuthorizerResponse(
                f"Authorizer '{auth_name}' contains an invalid or " f"missing '{_RESPONSE_IAM_STATEMENT}' from response"
            )

        validators = {
            _RESPONSE_IAM_ACTION: LambdaAuthorizerIAMPolicyPropertyValidator(_RESPONSE_IAM_ACTION, [str, list]),
            _RESPONSE_IAM_EFFECT: LambdaAuthorizerIAMPolicyPropertyValidator(_RESPONSE_IAM_EFFECT, [str]),
            _RESPONSE_IAM_RESOURCE: LambdaAuthorizerIAMPolicyPropertyValidator(_RESPONSE_IAM_RESOURCE, [str, list]),
        }

        for statement in all_statements:
            if not isinstance(statement, dict):
                raise InvalidLambdaAuthorizerResponse(
                    f"Authorizer '{auth_name}' policy document must be a list of objects"
                )

            for prop_name, validator in validators.items():
                if not validator.is_valid(statement):
                    raise InvalidLambdaAuthorizerResponse(
                        f"Authorizer '{auth_name}' policy document contains an invalid '{prop_name}'"
                    )
