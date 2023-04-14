"""
Handles the validation of identity sources
"""
import re

from samcli.local.apigw.route import Route


class IdentitySourceValidator:
    # match lowercase + uppercase + numbers + those 3 symbols, until the end of string
    API_GATEWAY_V1_QUERY_REGEX = re.compile(r"method\.request\.querystring\.[a-zA-Z0-9._-]+$")
    API_GATEWAY_V1_HEADER_REGEX = re.compile(r"method\.request\.header\.[a-zA-Z0-9._-]+$")
    API_GATEWAY_V1_CONTEXT_REGEX = re.compile(r"context\.[a-zA-Z0-9._-]+$")
    API_GATEWAY_V1_STAGE_REGEX = re.compile(r"stageVariables\.[a-zA-Z0-9._-]+$")

    API_GATEWAY_V2_QUERY_REGEX = re.compile(r"\$request\.querystring\.[a-zA-Z0-9._-]+$")
    API_GATEWAY_V2_HEADER_REGEX = re.compile(r"\$request\.header\.[a-zA-Z0-9._-]+$")
    API_GATEWAY_V2_CONTEXT_REGEX = re.compile(r"\$context\.[a-zA-Z0-9._-]+$")
    API_GATEWAY_V2_STAGE_REGEX = re.compile(r"\$stageVariables\.[a-zA-Z0-9._-]+$")

    API_GATEWAY_VALIDATION_LIST = {
        Route.API: [
            API_GATEWAY_V1_QUERY_REGEX,
            API_GATEWAY_V1_HEADER_REGEX,
            API_GATEWAY_V1_CONTEXT_REGEX,
            API_GATEWAY_V1_STAGE_REGEX,
        ],
        Route.HTTP: [
            API_GATEWAY_V2_QUERY_REGEX,
            API_GATEWAY_V2_HEADER_REGEX,
            API_GATEWAY_V2_CONTEXT_REGEX,
            API_GATEWAY_V2_STAGE_REGEX,
        ],
    }

    @staticmethod
    def validate_identity_source(identity_source: str, event_type: str = Route.API) -> bool:
        """
        Validates if the identity source is valid for the provided event type

        Parameters
        ----------
        identity_source: str
            The identity source to validate
        event_type: str
            The type of API Gateway to validate against (API or HTTP)

        Returns
        -------
        bool
            True if the identity source is valid
        """
        for regex in IdentitySourceValidator.API_GATEWAY_VALIDATION_LIST[event_type]:
            if regex.match(identity_source):
                return True

        return False
