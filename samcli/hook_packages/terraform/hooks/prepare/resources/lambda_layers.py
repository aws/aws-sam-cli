from typing import Dict, List, Tuple

from samcli.hook_packages.terraform.hooks.prepare.resources.code_resource_utils import (
    _add_lambda_resource_code_path_to_code_map,
)
from samcli.hook_packages.terraform.hooks.prepare.types import (
    CodeResourceProperties,
    ResourceTranslationProperties,
)


class LambdaLayerVersionProperties(CodeResourceProperties):
    def __init__(self):
        super(LambdaLayerVersionProperties, self).__init__()

    def collect(self, properties: ResourceTranslationProperties):
        self.terraform_resources[properties.logical_id] = properties.resource

    def add_lambda_resources_to_code_map(
        self,
        properties: ResourceTranslationProperties,
        translated_properties: Dict,
        lambda_resources_to_code_map: Dict[str, List[Tuple[Dict, str]]],
    ):
        planned_value_layer_code_path = translated_properties.get("Content")
        _add_lambda_resource_code_path_to_code_map(
            properties.config_resource,
            "layer",
            lambda_resources_to_code_map,
            properties.logical_id,
            planned_value_layer_code_path,
            "filename",
            properties.translated_resource,
        )
