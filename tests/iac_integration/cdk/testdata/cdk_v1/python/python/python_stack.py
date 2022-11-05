import os
from pathlib import Path
from typing import cast

from aws_cdk import core as cdk, aws_lambda as lambda1, aws_apigateway as apigw, aws_logs as logs
from aws_cdk.aws_apigateway import LambdaIntegration
from aws_cdk.aws_lambda_nodejs import NodejsFunction, BundlingOptions as NodeJsBundlingOptions
from aws_cdk.aws_lambda_go import GoFunction, BundlingOptions as GoBundlingOptions
from aws_cdk.aws_lambda_python import PythonFunction, PythonLayerVersion
from aws_cdk.aws_iam import Role, ServicePrincipal, PolicyStatement
from aws_cdk.aws_lambda import CfnFunction, CfnLayerVersion
from aws_cdk.core import BundlingOptions

from .nested_stack import NestedStack1


class PythonStack(cdk.Stack):
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

        # Lambda LayerVersion with bundled Asset that will be built by CDK
        bundled_layer_version_python_runtime = lambda1.LayerVersion(
            self,
            "BundledLayerVersionPythonRuntime",
            compatible_runtimes=[
                lambda1.Runtime.PYTHON_3_7,
                lambda1.Runtime.PYTHON_3_8,
                lambda1.Runtime.PYTHON_3_9,
            ],
            code=lambda1.Code.from_asset(
                "../../src/python/layers/BundledLayerVersion",
                bundling=BundlingOptions(
                    command=[
                        "/bin/sh",
                        "-c",
                        "rm -rf /tmp/asset-input && mkdir /tmp/asset-input && cp * /tmp/asset-input && cd /tmp/asset-input && pip install -r requirements.txt -t . && mkdir /asset-output/python && cp -R /tmp/asset-input/* /asset-output/python",
                    ],
                    image=lambda1.Runtime.PYTHON_3_7.bundling_image,
                    user="root",
                ),
            ),
        )

        # ZIP package type Functions
        # Functions Built by CDK - Runtime Functions Constructs
        python_function = PythonFunction(
            self,
            "PythonFunction",
            entry="../../src/python/PythonFunctionConstruct",
            index="app.py",
            handler="lambda_handler",
            runtime=lambda1.Runtime.PYTHON_3_9,
            function_name="pythonFunc",  # we need the name to use it in the API definition file
            log_retention=logs.RetentionDays.THREE_MONTHS,
            layers=[python_layer_version, layer_version],
            tracing=lambda1.Tracing.ACTIVE,
        )

        # Normal Lambda Function Construct - Python Runtime
        function_python_runtime = lambda1.Function(
            self,
            "FunctionPythonRuntime",
            runtime=lambda1.Runtime.PYTHON_3_7,
            code=lambda1.Code.from_asset("../../src/python/FunctionConstruct"),
            handler="app.lambda_handler",
            layers=[python_layer_version, layer_version],
            tracing=lambda1.Tracing.ACTIVE,
        )

        # Normal Lambda Function Construct - Python Runtime - with skip build metadata
        pre_built_function_python_runtime = lambda1.Function(
            self,
            "PreBuiltFunctionPythonRuntime",
            runtime=lambda1.Runtime.PYTHON_3_7,
            code=lambda1.Code.from_asset("../../src/python/BuiltFunctionConstruct"),
            handler="app.lambda_handler",
            layers=[python_layer_version, layer_version],
            tracing=lambda1.Tracing.ACTIVE,
        )
        # add SkipBuild Metadata, so SAM will skip building self function
        cfn_pre_built_function_python_runtime = cast(CfnFunction, pre_built_function_python_runtime.node.default_child)
        cfn_pre_built_function_python_runtime.add_metadata("SkipBuild", True)

        # Normal Lambda Function with bundled Asset will be built by CDK
        bundled_function_python_runtime = lambda1.Function(
            self,
            "BundledFunctionPythonRuntime",
            runtime=lambda1.Runtime.PYTHON_3_7,
            code=lambda1.Code.from_asset(
                "../../src/python/BundledFunctionConstruct/",
                bundling=BundlingOptions(
                    command=[
                        "/bin/sh",
                        "-c",
                        "rm -rf /tmp/asset-input && mkdir /tmp/asset-input && cp * /tmp/asset-input && cd /tmp/asset-input && pip install -r requirements.txt -t . && cp -R /tmp/asset-input/* /asset-output",
                    ],
                    image=lambda1.Runtime.PYTHON_3_7.bundling_image,
                    user="root",
                ),
            ),
            handler="app.lambda_handler",
            layers=[
                bundled_layer_version_python_runtime,
                python_layer_version,
            ],
            timeout=cdk.Duration.seconds(120),
            tracing=lambda1.Tracing.ACTIVE,
        )

        # NodeJs Runtime
        # Layers
        layer_version_node_js_runtime = lambda1.LayerVersion(
            self,
            "LayerVersionNodeJsRuntime",
            compatible_runtimes=[
                lambda1.Runtime.NODEJS_14_X,
            ],
            code=lambda1.Code.from_asset("../../src/nodejs/layers/LayerVersion"),
        )
        # add SAM metadata to build layer
        cfn_layer_version_node_js_runtime = cast(CfnLayerVersion, layer_version_node_js_runtime.node.default_child)
        cfn_layer_version_node_js_runtime.add_metadata("BuildMethod", "nodejs14.x")

        nodejs_function = NodejsFunction(
            self,
            "NodejsFunction",
            entry=os.path.join(
                Path(__file__).resolve().parents[0], "../../../src/nodejs/NodeJsFunctionConstruct/app.ts"
            ),
            deps_lock_file_path=os.path.join(
                Path(__file__).resolve().parents[0], "../../../src/nodejs/NodeJsFunctionConstruct/package-lock.json"
            ),
            bundling=NodeJsBundlingOptions(
                external_modules=["/opt/nodejs/layer_version_dependency"],
            ),
            handler="lambdaHandler",
            layers=[layer_version_node_js_runtime],
            tracing=lambda1.Tracing.ACTIVE,
        )

        # Normal Lambda Function Construct - NodeJs Runtime
        function_node_js_runtime = lambda1.Function(
            self,
            "FunctionNodeJsRuntime",
            runtime=lambda1.Runtime.NODEJS_14_X,
            code=lambda1.Code.from_asset("../../src/nodejs/FunctionConstruct"),
            handler="app.lambdaHandler",
            layers=[layer_version_node_js_runtime],
            tracing=lambda1.Tracing.ACTIVE,
        )

        # Normal Lambda Function Construct - NodeJs Runtime - with skip build metadata
        pre_built_function_node_js_runtime = lambda1.Function(
            self,
            "PreBuiltFunctionNodeJsRuntime",
            runtime=lambda1.Runtime.NODEJS_14_X,
            code=lambda1.Code.from_asset("../../src/nodejs/BuiltFunctionConstruct"),
            handler="app.lambdaHandler",
            layers=[layer_version_node_js_runtime],
            tracing=lambda1.Tracing.ACTIVE,
        )
        # add SkipBuild Metadata, so SAM will skip building self function
        cfn_pre_built_function_node_js_runtime = cast(
            CfnFunction, pre_built_function_node_js_runtime.node.default_child
        )
        cfn_pre_built_function_node_js_runtime.add_metadata("SkipBuild", True)

        # Go Runtime
        go_function = GoFunction(
            self,
            "GoFunction",
            entry="../../src/go/GoFunctionConstruct",
            bundling=GoBundlingOptions(
                forced_docker_bundling=True,
            ),
        )

        # Normal Lambda Function Construct - Go Runtime
        function_go_runtime = lambda1.Function(
            self,
            "FunctionGoRuntime",
            runtime=lambda1.Runtime.GO_1_X,
            code=lambda1.Code.from_asset("../../src/go/FunctionConstruct"),
            handler="FunctionConstruct",
        )

        # Image Package Type Functions

        # One way to define an Image Package Type Function
        docker_image_function = lambda1.DockerImageFunction(
            self,
            "DockerImageFunction",
            code=lambda1.DockerImageCode.from_image_asset(
                directory="../../src/docker/DockerImageFunctionConstruct",
                file="Dockerfile",
            ),
            tracing=lambda1.Tracing.ACTIVE,
        )

        # another way
        function_image_asset = lambda1.Function(
            self,
            "FunctionImageAsset",
            code=lambda1.Code.from_asset_image(
                directory="../../src/docker/FunctionConstructWithImageAssetCode",
                file="Dockerfile",
            ),
            handler=lambda1.Handler.FROM_IMAGE,
            runtime=lambda1.Runtime.FROM_IMAGE,
            tracing=lambda1.Tracing.ACTIVE,
        )

        # both ways work when 'file' is a path via subfolders to the Dockerfile
        # this is useful when multiple docker images share some common code
        docker_image_function_with_shared_code = lambda1.DockerImageFunction(
            self,
            "DockerImageFunctionWithSharedCode",
            code=lambda1.DockerImageCode.from_image_asset(
                directory="../../src/docker/ImagesWithSharedCode",
                file="DockerImageFunctionWithSharedCode/Dockerfile",
            ),
            tracing=lambda1.Tracing.ACTIVE,
        )

        function_image_asset_with_shared_code = lambda1.Function(
            self,
            "FunctionImageAssetWithSharedCode",
            code=lambda1.Code.from_asset_image(
                directory="../../src/docker/ImagesWithSharedCode",
                file="FunctionImageAssetWithSharedCode/Dockerfile",
            ),
            handler=lambda1.Handler.FROM_IMAGE,
            runtime=lambda1.Runtime.FROM_IMAGE,
            tracing=lambda1.Tracing.ACTIVE,
        )

        # Rest APIs

        # Spec Rest Api
        apigw.SpecRestApi(
            self,
            "SpecRestAPI",
            api_definition=apigw.ApiDefinition.from_asset("../../src/rest-api-definition.yaml"),
        )

        # Role to be used as credentials for the Spec rest APi
        # it is used inside the spec rest api definition file
        Role(
            self,
            "SpecRestApiRole",
            assumed_by=ServicePrincipal("apigateway.amazonaws.com"),
            role_name="SpecRestApiRole",
        ).add_to_policy(
            PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=["*"],
            )
        )

        # Rest Api
        rest_api = apigw.RestApi(self, "RestAPI")
        normal_root_resource = rest_api.root.add_resource("restapis").add_resource("normal")
        normal_root_resource.add_resource("pythonFunction").add_method("GET", LambdaIntegration(python_function))
        normal_root_resource.add_resource("functionPythonRuntime").add_method(
            "GET", LambdaIntegration(function_python_runtime)
        )
        normal_root_resource.add_resource("preBuiltFunctionPythonRuntime").add_method(
            "GET", LambdaIntegration(pre_built_function_python_runtime)
        )
        normal_root_resource.add_resource("bundledFunctionPythonRuntime").add_method(
            "GET", LambdaIntegration(bundled_function_python_runtime)
        )
        normal_root_resource.add_resource("nodejsFunction").add_method("GET", LambdaIntegration(nodejs_function))
        normal_root_resource.add_resource("functionNodeJsRuntime").add_method(
            "GET", LambdaIntegration(function_node_js_runtime)
        )
        normal_root_resource.add_resource("preBuiltFunctionNodeJsRuntime").add_method(
            "GET", LambdaIntegration(pre_built_function_node_js_runtime)
        )
        normal_root_resource.add_resource("goFunction").add_method("GET", LambdaIntegration(go_function))
        normal_root_resource.add_resource("functionGoRuntime").add_method("GET", LambdaIntegration(function_go_runtime))
        normal_root_resource.add_resource("dockerImageFunction").add_method(
            "GET", LambdaIntegration(docker_image_function)
        )
        normal_root_resource.add_resource("functionImageAsset").add_method(
            "GET", LambdaIntegration(function_image_asset)
        )
        normal_root_resource.add_resource("dockerImageFunctionWithSharedCode").add_method(
            "GET", LambdaIntegration(docker_image_function_with_shared_code)
        )
        normal_root_resource.add_resource("functionImageAssetWithSharedCode").add_method(
            "GET", LambdaIntegration(function_image_asset_with_shared_code)
        )

        # Nested Stack
        NestedStack1(self, "NestedStack")
