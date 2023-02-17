"""
StackBuilder implementation for nested stack
"""
import re
from typing import cast

from samcli.lib.bootstrap.stack_builder import AbstractStackBuilder
from samcli.lib.providers.provider import Function
from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.resources import AWS_CLOUDFORMATION_STACK, AWS_SERVERLESS_LAYERVERSION

CREATED_BY_METADATA_KEY = "CreatedBy"
CREATED_BY_METADATA_VALUE = "AWS SAM CLI sync command"
NON_ALPHANUM_REGEX = re.compile(r"\W+")


class NestedStackBuilder(AbstractStackBuilder):
    """
    CFN/SAM Template creator for nested stack
    """

    def __init__(self):
        super().__init__("AWS SAM CLI Nested Stack for Auto Dependency Layer Creation")
        self.add_metadata(CREATED_BY_METADATA_KEY, CREATED_BY_METADATA_VALUE)

    def is_any_function_added(self) -> bool:
        return bool(self._template_dict.get("Resources", {}))

    def add_function(
        self,
        stack_name: str,
        layer_contents_folder: str,
        function: Function,
    ) -> str:
        layer_logical_id = self.get_layer_logical_id(function.full_path)
        layer_name = self.get_layer_name(stack_name, function.full_path)

        self.add_resource(
            layer_logical_id,
            self._get_layer_dict(function.full_path, layer_name, layer_contents_folder, cast(str, function.runtime)),
        )
        self.add_output(layer_logical_id, {"Ref": layer_logical_id})
        return layer_logical_id

    @staticmethod
    def get_layer_logical_id(function_logical_id: str) -> str:
        function_logical_id_hash = str_checksum(function_logical_id)
        sanitized_function_logical_id = NestedStackBuilder._get_logical_id_compliant_str(function_logical_id)
        return f"{sanitized_function_logical_id[:48]}{function_logical_id_hash[:8]}DepLayer"

    @staticmethod
    def get_layer_name(stack_name: str, function_logical_id: str) -> str:
        function_logical_id_hash = str_checksum(function_logical_id)
        sanitized_function_logical_id = NestedStackBuilder._get_logical_id_compliant_str(function_logical_id)
        stack_name_hash = str_checksum(stack_name)
        return (
            f"{stack_name[:16]}{stack_name_hash[:8]}-{sanitized_function_logical_id[:22]}{function_logical_id_hash[:8]}"
            f"-DepLayer"
        )

    @staticmethod
    def _get_layer_dict(function_logical_id: str, layer_name: str, layer_contents_folder: str, function_runtime: str):
        return {
            "Type": AWS_SERVERLESS_LAYERVERSION,
            "Properties": {
                "LayerName": layer_name,
                "Description": f"Auto created layer for dependencies of function {function_logical_id}",
                "ContentUri": layer_contents_folder,
                "RetentionPolicy": "Delete",
                "CompatibleRuntimes": [function_runtime],
            },
            "Metadata": {CREATED_BY_METADATA_KEY: CREATED_BY_METADATA_VALUE},
        }

    @staticmethod
    def get_nested_stack_reference_resource(nested_template_location):
        return {
            "Type": AWS_CLOUDFORMATION_STACK,
            "DeletionPolicy": "Delete",
            "Properties": {"TemplateURL": nested_template_location},
            "Metadata": {CREATED_BY_METADATA_KEY: CREATED_BY_METADATA_VALUE},
        }

    @staticmethod
    def _get_logical_id_compliant_str(function_logical_id: str):
        """
        Removes all non-alphanumeric chars to make it usable for resource name definition
        https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/resources-section-structure.html
        """
        return NON_ALPHANUM_REGEX.sub("", function_logical_id)
