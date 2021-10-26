"""
Provide a CFN implementation of IaCPluginInterface
"""

import os
import logging
from typing import List, Optional
from urllib.parse import unquote, urlparse

import jmespath

from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.iac.constants import PARAMETER_OVERRIDES, GLOBAL_PARAMETER_OVERRIDES
from samcli.lib.iac.plugins_interfaces import (
    Asset,
    DictSection,
    DictSectionItem,
    IaCPluginInterface,
    ImageAsset,
    S3Asset,
    SamCliContext,
    SamCliProject,
    Stack,
    LookupPath,
)
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.utils.resources import (
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_IMAGE_COMPONENT,
    RESOURCES_WITH_LOCAL_PATHS,
    NESTED_STACKS_RESOURCES,
    AWS_SERVERLESS_FUNCTION,
    AWS_LAMBDA_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_LAMBDA_LAYERVERSION,
)
from samcli.commands._utils.template import get_template_data
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider, is_local_path, get_local_path

LOG = logging.getLogger(__name__)

PARENT_STACK_TEMPLATE_PATH_KEY = "parent_stack_template_path"
TEMPLATE_PATH_KEY = "template_path"
TEMPLATE_BUILD_PATH_KEY = "template_build_path"

BASE_DIR_RESOURCES = [
    AWS_SERVERLESS_FUNCTION,
    AWS_LAMBDA_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_LAMBDA_LAYERVERSION,
]


class CfnIacImplementation(IaCPluginInterface):
    """
    CFN implementation for the plugins interface.
    read_project parses the CFN and returns a SamCliProject object
    write_project writes the updated project
        back to the build dir and returns true if successful
    update_packaged_locations updates the package locations and
        returns true if successful
    get_iac_file_types returns a list of file types/patterns associated with
        the CFN project type
    """

    def __init__(self, context: SamCliContext):
        self._template_file = context.command_options_map["template_file"]
        self._base_dir = context.command_options_map.get("base_dir", None)
        super().__init__(context)

    def read_project(self, lookup_paths: List[LookupPath]) -> SamCliProject:
        stack = self._build_stack(self._template_file)
        return SamCliProject([stack])

    def write_project(self, project: SamCliProject, build_dir: str) -> bool:
        # TODO
        pass

    def update_packaged_locations(self, stack: Stack) -> bool:
        # TODO
        pass

    # pylint: disable=too-many-branches
    def _build_stack(self, path: str, is_nested: bool = False, name: Optional[str] = None) -> Stack:
        asset: Asset
        assets: List[Asset] = []

        if os.path.islink(path):
            path = os.path.realpath(path)

        base_dir = self._base_dir or os.path.dirname(path)

        stack = Stack(is_nested=is_nested, name=name, assets=assets, origin_dir=os.path.dirname(path))

        template_dict = get_template_data(path)
        options = self._context.command_options_map
        resolved_stack = SamBaseProvider.get_resolved_template_dict(
            template_dict,
            SamLocalStackProvider.merge_parameter_overrides(
                options.get(PARAMETER_OVERRIDES), options.get(GLOBAL_PARAMETER_OVERRIDES)
            ),
            normalize_resource_metadata=False,
        )
        for key, value in resolved_stack.items():
            stack[key] = value

        resources_section = stack.get("Resources", DictSection())
        for resource in resources_section.section_items:
            resource_id = resource.item_id
            resource_type = resource.get("Type", None)
            properties = resource.get("Properties", {})
            package_type = properties.get("PackageType", ZIP)

            resource_assets: List[Asset] = []

            if resource_type in NESTED_STACKS_RESOURCES:
                nested_stack = self._extract_nested_stack(path, resource_id, properties, resource_type)
                resource.nested_stack = nested_stack

            if resource_type in RESOURCES_WITH_LOCAL_PATHS:
                for path_prop_name in RESOURCES_WITH_LOCAL_PATHS[resource_type]:
                    asset_path = jmespath.search(path_prop_name, properties)
                    if is_local_path(asset_path) and package_type == ZIP:
                        reference_path = base_dir if resource_type in BASE_DIR_RESOURCES else os.path.dirname(path)
                        asset_path = get_local_path(asset_path, reference_path)
                        asset = S3Asset(source_path=asset_path, source_property=path_prop_name)
                        resource_assets.append(asset)
                        stack.assets.append(asset)

            if resource_type in RESOURCES_WITH_IMAGE_COMPONENT:
                for path_prop_name in RESOURCES_WITH_IMAGE_COMPONENT[resource_type]:
                    asset_path = jmespath.search(path_prop_name, properties)
                    if asset_path and package_type == IMAGE:
                        asset = ImageAsset(source_local_image=asset_path, source_property=path_prop_name)
                        resource_assets.append(asset)
                        stack.assets.append(asset)

            resource.assets = resource_assets

        metadata_section = stack.get("Metadata", DictSection())
        for metadata in metadata_section.section_items:
            if not isinstance(metadata, DictSectionItem):
                continue
            metadata_type = metadata.item_id
            metadata_body = metadata.body
            metadata_assets: List[Asset] = []
            if metadata_type in METADATA_WITH_LOCAL_PATHS:
                for path_prop_name in METADATA_WITH_LOCAL_PATHS[metadata_type]:
                    asset_path = jmespath.search(path_prop_name, metadata_body)
                    asset = S3Asset(source_path=asset_path, source_property=path_prop_name)
                    metadata_assets.append(asset)
                    stack.assets.append(asset)

            metadata.assets = metadata_assets

        stack.extra_details[TEMPLATE_PATH_KEY] = path
        return stack

    def _extract_nested_stack(
        self, parent_stack_template_path, resource_id, properties, resource_type
    ) -> Optional[Stack]:
        if not properties:
            return None

        nested_stack_location_property_name = NESTED_STACKS_RESOURCES[resource_type]
        nested_stack_template_location = properties.get(nested_stack_location_property_name, None)

        if not is_local_path(nested_stack_template_location):
            return None

        if nested_stack_template_location.startswith("file://"):
            nested_stack_template_location = unquote(urlparse(nested_stack_template_location).path)
        else:
            nested_stack_template_location = SamLocalStackProvider.normalize_resource_path(
                os.path.dirname(parent_stack_template_path), nested_stack_template_location
            )
        nested_stack = self._build_stack(nested_stack_template_location, True, resource_id)
        nested_stack.extra_details[PARENT_STACK_TEMPLATE_PATH_KEY] = parent_stack_template_path
        return nested_stack

    @staticmethod
    def get_iac_file_patterns() -> List[str]:
        return ["template.yaml", "template.yml", "template.json"]
