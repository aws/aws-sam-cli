from typing import cast

from aws_cdk import (
    core as cdk,
    aws_lambda as lambda1,
)
from aws_cdk.aws_apigatewayv2 import HttpApi, HttpMethod
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from aws_cdk.aws_lambda import CfnLayerVersion
from aws_cdk.aws_lambda_python import PythonLayerVersion, PythonFunction


class NestedStack1(cdk.NestedStack):
    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Python Runtime
        # Layers
        python_layer_version = PythonLayerVersion(
            self,
            "PythonLayerVersion",
            compatible_runtimes=[
                lambda1.Runtime.PYTHON_3_7,
                lambda1.Runtime.PYTHON_3_8,
                lambda1.Runtime.PYTHON_3_9,
            ],
            entry="../../src/python/layers/PythonLayerVersion",
        )
        layer_version = lambda1.LayerVersion(
            self,
            "LayerVersion",
            compatible_runtimes=[
                lambda1.Runtime.PYTHON_3_7,
                lambda1.Runtime.PYTHON_3_8,
                lambda1.Runtime.PYTHON_3_9,
            ],
            code=lambda1.Code.from_asset("../../src/python/layers/LayerVersion"),
        )
        # add SAM metadata to build layer
        cfn_layer_version = cast(CfnLayerVersion, layer_version.node.default_child)
        cfn_layer_version.add_metadata("BuildMethod", "python3.7")

        # ZIP package type Functions
        # Functions Built by CDK - Runtime Functions Constructs
        nested_python_function = PythonFunction(
            self,
            "NestedPythonFunction",
            entry="../../src/python/NestedPythonFunctionConstruct",
            index="app.py",
            handler="lambda_handler",
            runtime=lambda1.Runtime.PYTHON_3_9,
            layers=[python_layer_version, layer_version],
            tracing=lambda1.Tracing.ACTIVE,
        )
        http_api = HttpApi(self, "httpAPi")

        http_api.add_routes(
            path="/httpapis/nestedPythonFunction",
            methods=[HttpMethod.GET],
            integration=HttpLambdaIntegration("httpApiRandomNameIntegration", nested_python_function),
        )
