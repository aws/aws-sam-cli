"""Module containing logic specific to Lambda layer resource handling during the prepare hook execution"""

from typing import Dict, List, Tuple

from samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils import (
    _add_lambda_resource_code_path_to_code_map,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    CodeResourceProperties,
    ResourceTranslationProperties,
)


class LambdaLayerVersionProperties(CodeResourceProperties):
    CFN_CODE_FIELD = "Content"

    def __init__(self):
        super(LambdaLayerVersionProperties, self).__init__()

    def add_lambda_resources_to_code_map(
        self,
        properties: ResourceTranslationProperties,
        translated_properties: Dict,
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
    ):
        """
        Resolves the relevant code properties for an AWS::Lambda::LayerVersion from a Terraform
        aws_lambda_layer_version and then stores that property in the lambda_resources_to_code_map.

        Parameters
        ----------
        properties: ResourceTranslationProperties
            Properties acquired specific to an aws_lambda_layer_version
            resource when iterating through a Terraform module
        translated_properties: Dict
            A dictionary of CloudFormation properties that were translated by the hook from the Terraform plan file
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]]
            A map storing all the Lambda code properties
        """
        planned_value_layer_code_path = translated_properties.get(self.CFN_CODE_FIELD)
        _add_lambda_resource_code_path_to_code_map(
            properties.config_resource,
            "layer",
            lambda_resources_to_code_map,
            properties.logical_id,
            planned_value_layer_code_path,
            "filename",
            properties.translated_resource,
        )
