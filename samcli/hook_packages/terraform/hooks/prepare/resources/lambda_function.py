from typing import Dict, List, Tuple

from samcli.hook_packages.terraform.hooks.prepare.resource_linking import _get_configuration_address
from samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils import (
    _add_lambda_resource_code_path_to_code_map,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    CodeResourceProperties,
    ResourceTranslationProperties,
)
from samcli.lib.utils.packagetype import IMAGE, ZIP


class LambdaFunctionProperties(CodeResourceProperties):
    def __init__(self):
        super(LambdaFunctionProperties, self).__init__()

    def collect(self, properties: ResourceTranslationProperties):
        resolved_config_address = _get_configuration_address(properties.resource_full_address)
        matched_lambdas = self.cfn_resources.get(resolved_config_address, [])
        matched_lambdas.append(properties.translated_resource)
        self.cfn_resources[resolved_config_address] = matched_lambdas
        self.terraform_config[resolved_config_address] = properties.config_resource

    def add_lambda_resources_to_code_map(
        self,
        properties: ResourceTranslationProperties,
        translated_properties: Dict,
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
    ):
        resource_type = translated_properties.get("PackageType", ZIP)
        resource_type_constants = {ZIP: ("zip", "filename"), IMAGE: ("image", "image_uri")}
        planned_value_function_code_path = (
            translated_properties.get("Code")
            if resource_type == ZIP
            else translated_properties.get("Code", {}).get("ImageUri")
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
