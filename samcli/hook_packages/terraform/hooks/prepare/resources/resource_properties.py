from typing import Dict

from samcli.hook_packages.terraform.hooks.prepare.property_builder import (
    TF_AWS_LAMBDA_FUNCTION,
    TF_AWS_LAMBDA_LAYER_VERSION,
)
from samcli.hook_packages.terraform.hooks.prepare.resources.lambda_function import LambdaFunctionProperties
from samcli.hook_packages.terraform.hooks.prepare.resources.lambda_layers import LambdaLayerVersionProperties
from samcli.hook_packages.terraform.hooks.prepare.types import ResourceProperties


def get_resource_property_mapping() -> Dict[str, ResourceProperties]:
    return {
        TF_AWS_LAMBDA_LAYER_VERSION: LambdaLayerVersionProperties(),
        TF_AWS_LAMBDA_FUNCTION: LambdaFunctionProperties(),
    }
