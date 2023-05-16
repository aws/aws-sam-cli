"""Module containing logic specific to Lambda function resource handling during the prepare hook execution"""
from typing import Dict, List, Tuple

from samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils import (
    _add_lambda_resource_code_path_to_code_map,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    CodeResourceProperties,
    ResourceTranslationProperties,
)
from samcli.lib.utils.packagetype import IMAGE, ZIP


class LambdaFunctionProperties(CodeResourceProperties):
    RESOURCE_TYPE_FIELD = "PackageType"
    CFN_CODE_FIELD = "Code"
    CFN_IMAGE_FIELD = "ImageUri"

    def __init__(self):
        super(LambdaFunctionProperties, self).__init__()

    def add_lambda_resources_to_code_map(
        self,
        properties: ResourceTranslationProperties,
        translated_properties: Dict,
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
    ):
        """
        Resolves the relevant code properties for an AWS::Lambda::Function from a Terraform aws_lambda_function
        and then stores that property in the lambda_resources_to_code_map.

        Parameters
        ----------
        properties: ResourceTranslationProperties
            Properties acquired specific to an aws_lambda_function resource when iterating through a Terraform module
        translated_properties: Dict
            A dictionary of CloudFormation properties that were translated by the hook from the Terraform plan file
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]]
            A map storing all the Lambda code properties
        """
        resource_type = translated_properties.get(self.RESOURCE_TYPE_FIELD, ZIP)
        resource_type_constants = {ZIP: ("zip", "filename"), IMAGE: ("image", "image_uri")}
        planned_value_function_code_path = (
            translated_properties.get(self.CFN_CODE_FIELD)
            if resource_type == ZIP
            else translated_properties.get(self.CFN_CODE_FIELD, {}).get(self.CFN_IMAGE_FIELD)
        )
        func_type, tf_code_property = resource_type_constants[resource_type]

        _add_lambda_resource_code_path_to_code_map(
            properties.config_resource,
            func_type,
            lambda_resources_to_code_map,
            properties.logical_id,
            planned_value_function_code_path,
            tf_code_property,
            properties.translated_resource,
        )
