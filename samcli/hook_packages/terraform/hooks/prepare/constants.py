"""
Constants related to the Terraform prepare hook.
"""
import re

from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION
from samcli.lib.utils.resources import AWS_LAMBDA_LAYERVERSION as CFN_AWS_LAMBDA_LAYER_VERSION

SAM_METADATA_RESOURCE_NAME_ATTRIBUTE = "resource_name"

CFN_CODE_PROPERTIES = {
    CFN_AWS_LAMBDA_FUNCTION: "Code",
    CFN_AWS_LAMBDA_LAYER_VERSION: "Content",
}
COMPILED_REGULAR_EXPRESSION = re.compile(r"\[[^\[\]]*\]")
