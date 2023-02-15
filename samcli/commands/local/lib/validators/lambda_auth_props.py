"""
Module to help validate Lambda Authorizer properties
"""
from abc import ABC, abstractmethod
import logging
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.commands.local.lib.swagger.integration_uri import LambdaUri
from samcli.lib.providers.cfn_api_provider import CfnApiProvider
from samcli.local.apigw.local_apigw_service import LambdaAuthorizer


LOG = logging.getLogger(__name__)


class BaseLambdaAuthorizerValidator(ABC):
    @abstractmethod
    def validate(logical_id: str, resource: dict) -> bool:
        """
        Validates if all the required properties for a Lambda Authorizer are present and valid.

        Parameters
        ----------
        logical_id: str
            The logical ID of the authorizer
        resource: dict
            The resource dictionary for the authorizer containing the `Properties`

        Returns
        -------
        bool
            True if the `Properties` contains all the required key values
        """
        pass

    @staticmethod
    def _validate_common_properties(logical_id: str, properties: dict, type_key: str, api_key: str):
        """
        Validates if the common required properties are present and valid, will raise an exception
        if they are missing or invalid.

        Parameters
        ----------
        logical_id: str
            The logical ID of the authorizer
        properties: dict
            The `Properties` dictionary for the authorizer
        type_key: str
            They authorizer type key to search for
        api_key: str
            The API Gateway reference key to search for
        """
        authorizer_type = properties.get(type_key)
        api_id = properties.get(api_key)
        name = properties.get(CfnApiProvider._AUTHORIZER_NAME)

        if not authorizer_type:
            raise InvalidSamTemplateException(
                f"Authorizer '{logical_id}' is missing the '{type_key}' "
                "property, an Authorizer type must be defined."
            )

        if not api_id:
            raise InvalidSamTemplateException(
                f"Authorizer '{logical_id}' is missing the '{api_key}' " "property, this must be defined."
            )

        if not name:
            raise InvalidSamTemplateException(
                f"Authorizer '{logical_id}' is missing the '{CfnApiProvider._AUTHORIZER_NAME}' "
                "property, the Name must be defined."
            )


class LambdaAuthorizerV1Validator(BaseLambdaAuthorizerValidator):
    @staticmethod
    def validate(
        logical_id: str,
        resource: dict,
    ):
        """
        Validates if all the required properties for a Lambda Authorizer V1 are present and valid.

        Parameters
        ----------
        logical_id: str
            The logical ID of the authorizer
        resource: dict
            The resource dictionary for the authorizer containing the `Properties`

        Returns
        -------
        bool
            True if the `Properties` contains all the required key values
        """
        properties = resource.get("Properties", {})
        authorizer_type = properties.get(CfnApiProvider._AUTHORIZER_TYPE, "")
        authorizer_uri = properties.get(CfnApiProvider._AUTHORIZER_AUTHORIZER_URI)

        LambdaAuthorizerV1Validator._validate_common_properties(
            logical_id, properties, CfnApiProvider._AUTHORIZER_TYPE, CfnApiProvider._AUTHORIZER_REST_API
        )

        # (lucashuy) AWS SAM CLI keeps references to types as lowercase strings
        # while they are defined as uppercase strings in CFN
        # this is to just validate that they are provided as upper case strings
        if authorizer_type not in [type.upper() for type in LambdaAuthorizer.VALID_TYPES]:
            LOG.warning(
                "Authorizer '%s' with type '%s' is currently not supported. "
                "Only Lambda Authorizers of type TOKEN and REQUEST are supported.",
                logical_id,
                authorizer_type,
            )
            return False

        if not authorizer_uri:
            raise InvalidSamTemplateException(
                f"Authorizer '{logical_id}' is missing the '{CfnApiProvider._AUTHORIZER_AUTHORIZER_URI}' "
                "property, a valid Lambda ARN must be provided."
            )

        function_name = LambdaUri.get_function_name(authorizer_uri)
        if not function_name:
            LOG.warning(
                "Was not able to resolve Lambda function ARN for Authorizer '%s'. "
                "Double check the ARN format, or use more simple intrinsics.",
                logical_id,
            )
            return False

        identity_source_template = properties.get(CfnApiProvider._AUTHORIZER_IDENTITY_SOURCE, None)

        if identity_source_template is None and authorizer_type == LambdaAuthorizer.TOKEN.upper():
            raise InvalidSamTemplateException(
                f"Lambda Authorizer '{logical_id}' of type TOKEN, must have "
                f"'{CfnApiProvider._AUTHORIZER_IDENTITY_SOURCE}' of type string defined."
            )

        # (lucashuy) (regarding this if statement and the one below this)
        # For API Gateway V1, an authorizer of type REQUEST can omit the identity sources
        # if caching is enabled. Made the decision to not test this behaviour, and instead
        # test if the it is a string.
        if identity_source_template is not None and not isinstance(identity_source_template, str):
            raise InvalidSamTemplateException(
                f"Lambda Authorizer '{logical_id}' contains an invalid '{CfnApiProvider._AUTHORIZER_IDENTITY_SOURCE}', "
                "it must be a comma-separated string."
            )

        validation_expression = properties.get(CfnApiProvider._AUTHORIZER_VALIDATION)

        if authorizer_type == LambdaAuthorizer.REQUEST.upper() and validation_expression:
            raise InvalidSamTemplateException(
                "Lambda Authorizer '%s' has '%s' property defined, but validation is only "
                "supported on TOKEN type authorizers." % (logical_id, CfnApiProvider._AUTHORIZER_VALIDATION)
            )

        return True


class LambdaAuthorizerV2Validator(BaseLambdaAuthorizerValidator):
    @staticmethod
    def validate(
        logical_id: str,
        resource: dict,
    ):
        """
        Validates if all the required properties for a Lambda Authorizer V2 are present and valid.

        Parameters
        ----------
        logical_id: str
            The logical ID of the authorizer
        resource: dict
            The resource dictionary for the authorizer containing the `Properties`

        Returns
        -------
        bool
            True if the `Properties` contains all the required key values
        """
        properties = resource.get("Properties", {})
        authorizer_type = properties.get(CfnApiProvider._AUTHORIZER_V2_TYPE, "")
        authorizer_uri = properties.get(CfnApiProvider._AUTHORIZER_AUTHORIZER_URI)

        LambdaAuthorizerV2Validator._validate_common_properties(
            logical_id, properties, CfnApiProvider._AUTHORIZER_V2_TYPE, CfnApiProvider._AUTHORIZER_V2_API
        )

        # (lucashuy) AWS SAM CLI keeps references to types as lowercase strings
        # while they are defined as uppercase strings in CFN
        # this is to just validate that they are provided as upper case strings
        if authorizer_type != LambdaAuthorizer.REQUEST.upper():
            LOG.warning(
                "Authorizer '%s' with type '%s' is currently not supported. "
                "Only Lambda Authorizers of type REQUEST are supported for API Gateway V2.",
                logical_id,
                authorizer_type,
            )
            return False

        if not authorizer_uri:
            raise InvalidSamTemplateException(
                f"Authorizer '{logical_id}' is missing the '{CfnApiProvider._AUTHORIZER_AUTHORIZER_URI}' "
                "property, a valid Lambda ARN must be provided."
            )

        function_name = LambdaUri.get_function_name(authorizer_uri)
        if not function_name:
            LOG.warning(
                "Was not able to resolve Lambda function ARN for Authorizer '%s'. "
                "Double check the ARN format, or use more simple intrinsics.",
                logical_id,
            )
            return False

        identity_sources = properties.get(CfnApiProvider._AUTHORIZER_IDENTITY_SOURCE, None)

        if not isinstance(identity_sources, list):
            raise InvalidSamTemplateException(
                f"Lambda Authorizer '{logical_id}' must have "
                f"'{CfnApiProvider._AUTHORIZER_IDENTITY_SOURCE}' of type list defined."
            )

        payload_version = properties.get(CfnApiProvider._AUTHORIZER_V2_PAYLOAD)

        if not payload_version in LambdaAuthorizer.PAYLOAD_VERSIONS:
            raise InvalidSamTemplateException(
                f"Lambda Authorizer '{logical_id}' is missing or invalid '{CfnApiProvider._AUTHORIZER_V2_PAYLOAD}'"
                ", it must be set to '1.0' or '2.0'"
            )

        simple_responses = properties.get(CfnApiProvider._AUTHORIZER_V2_SIMPLE_RESPONSE, False)

        if payload_version == LambdaAuthorizer.PAYLOAD_V1 and simple_responses:
            raise InvalidSamTemplateException(
                f"'{CfnApiProvider._AUTHORIZER_V2_SIMPLE_RESPONSE}' is only supported for '2.0' "
                f"payload format versions for Lambda Authorizer '{logical_id}'."
            )

        return True
