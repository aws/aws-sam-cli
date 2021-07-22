from aws_cdk import core as cdk

# For consistency with other languages, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import (
    core,
    aws_lambda as lambda_,
)


class CdkExampleLayerStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here
        requests_lambda_layer = lambda_.LayerVersion(
            scope=self,
            id="lambda-layer-version",
            code=lambda_.Code.from_asset("./lambda_layer"),
            layer_version_name="lambda_layer_version_example",
            description="Layer",
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_7],
        )

        lambda_function = lambda_.Function(
            scope=self,
            id="lambda-function",
            code=lambda_.Code.from_asset("./lambda_function"),
            runtime=lambda_.Runtime.PYTHON_3_7,
            handler="app.handler",
            layers=[requests_lambda_layer],
        )


