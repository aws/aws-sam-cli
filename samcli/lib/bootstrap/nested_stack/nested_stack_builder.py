"""
StackBuilder implementation for nested stack
"""
from typing import cast

from samcli.lib.bootstrap.stack_builder import AbstractStackBuilder
from samcli.lib.providers.provider import Function
from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.resources import AWS_SERVERLESS_LAYERVERSION, AWS_CLOUDFORMATION_STACK


class NestedStackBuilder(AbstractStackBuilder):
    """
    CFN/SAM Template creator for nested stack
    """

    def __init__(self):
        super().__init__("AWS SAM CLI Nested Stack for Auto Dependency Layer Creation")

    def is_any_function_added(self) -> bool:
        return bool(self._template_dict.get("Resources", {}))

    def add_function(
            self,
            stack_name: str,
            layer_contents_folder: str,
            function: Function,
    ) -> str:
        function_logical_id_hash = str_checksum(function.name)
        stack_name_hash = str_checksum(stack_name)
        layer_logical_id = f"{function.name[:48]}{function_logical_id_hash[:8]}DepLayer"
        layer_name = f"{stack_name[:16]}{stack_name_hash[:8]}{function.name[:22]}{function_logical_id_hash[:8]}" \
                     f"DepLayer"

        self.add_resource(
            layer_logical_id,
            self._get_layer_dict(
                function.name,
                layer_name,
                layer_contents_folder,
                cast(str, function.runtime)
            )
        )
        self.add_output(layer_logical_id, {"Ref": layer_logical_id})
        return layer_logical_id

    @staticmethod
    def _get_layer_dict(
            function_logical_id: str,
            layer_name: str,
            layer_contents_folder: str,
            function_runtime: str
    ):
        return {
            "Type": AWS_SERVERLESS_LAYERVERSION,
            "Properties": {
                "LayerName": layer_name,
                "Description": f"Auto created layer for dependencies of function {function_logical_id}",
                "ContentUri": layer_contents_folder,
                "RetentionPolicy": "Delete",
                "CompatibleRuntimes": [
                    function_runtime
                ]
            }
        }

    @staticmethod
    def get_nested_stack_reference_resource(nested_template_location):
        return {
            "Type": AWS_CLOUDFORMATION_STACK,
            "DeletionPolicy": "Delete",
            "Properties": {
                "TemplateURL": nested_template_location
            }
        }
