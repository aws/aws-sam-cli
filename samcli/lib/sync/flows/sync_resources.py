from typing import List

from samcli.lib.utils.resources import AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION, AWS_SERVERLESS_LAYERVERSION, \
    AWS_LAMBDA_LAYERVERSION, AWS_SERVERLESS_API, AWS_APIGATEWAY_RESTAPI, AWS_SERVERLESS_HTTPAPI, AWS_APIGATEWAY_V2_API, \
    AWS_SERVERLESS_STATEMACHINE, AWS_STEPFUNCTIONS_STATEMACHINE


class SyncCodeResources:
    """
    A class that records the supported resource types that can perform sync --code
    """

    _accepted_resources = [
        AWS_SERVERLESS_FUNCTION,
        AWS_LAMBDA_FUNCTION,
        AWS_SERVERLESS_LAYERVERSION,
        AWS_LAMBDA_LAYERVERSION,
        AWS_SERVERLESS_API,
        AWS_APIGATEWAY_RESTAPI,
        AWS_SERVERLESS_HTTPAPI,
        AWS_APIGATEWAY_V2_API,
        AWS_SERVERLESS_STATEMACHINE,
        AWS_STEPFUNCTIONS_STATEMACHINE,
    ]

    @classmethod
    def values(cls) -> List[str]:
        """
        A class getter to retrieve the accepted resource list

        Returns: List[str]
            The accepted resources list
        """
        return cls._accepted_resources