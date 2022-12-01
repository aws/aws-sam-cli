"""
Plugin to validate and convert local paths for CodeUri and DefinitionUri into mock S3 paths. This is required
for SAM Parser and Validator to work because the underlying SAM library expects the URIs to be S3 paths.
"""

from samtranslator.public.plugins import BasePlugin  # type: ignore[import]


class SupportLocalUriPlugin(BasePlugin):  # type: ignore[misc]

    _SERVERLESS_FUNCTION = "AWS::Serverless::Function"

    def __init__(self):  # type: ignore[no-untyped-def]
        """
        Initialize the plugin
        """
        super().__init__(SupportLocalUriPlugin.__name__)

    def on_before_transform_resource(self, logical_id, resource_type, resource_properties):  # type: ignore[no-untyped-def]

        if resource_type == self._SERVERLESS_FUNCTION and not resource_properties.get("CodeUri"):
            # If CodeUri is *not* present, set it to "." which is functionally equivalent
            resource_properties["CodeUri"] = "."
