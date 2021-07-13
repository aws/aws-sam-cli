"""
Cloud Formation IaC plugin implementation
"""
import os
import logging
from typing import List, Optional
from urllib.parse import unquote, urlparse

import jmespath

from samcli.commands._utils.resources import (
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_IMAGE_COMPONENT,
    RESOURCES_WITH_LOCAL_PATHS,
    NESTED_STACKS_RESOURCES,
)
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.iac.interface import (
    DictSectionItem,
    IacPlugin,
    ImageAsset,
    Project,
    LookupPath,
    Stack,
    DictSection,
    S3Asset,
    Asset,
    Resource,
)
from samcli.commands._utils.template import get_template_data, move_template
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider, is_local_path, get_local_path

LOG = logging.getLogger(__name__)

PARENT_STACK_TEMPLATE_PATH_KEY = "parent_stack_template_path"
TEMPLATE_PATH_KEY = "template_path"
TEMPLATE_BUILD_PATH_KEY = "template_build_path"

BASE_DIR_RESOURCES = [
    SamLocalStackProvider.SERVERLESS_FUNCTION,
    SamLocalStackProvider.LAMBDA_FUNCTION,
    SamLocalStackProvider.SERVERLESS_LAYER,
    SamLocalStackProvider.LAMBDA_LAYER,
]


class CfnIacPlugin(IacPlugin):
    def __init__(self, command_params: dict):
        self._template_file = command_params["template_file"]
        self._base_dir = command_params.get("base_dir", None)
        super().__init__(command_params)

    def get_project(self, lookup_paths: List[LookupPath]) -> Project:
        stacks = [self._build_stack(self._template_file)]

        return Project(stacks)

    # pylint: disable=too-many-branches
    def _build_stack(self, path: str, is_nested: bool = False, name: Optional[str] = None) -> Stack:
        assets: List[Asset] = []

        if os.path.islink(path):
            path = os.path.realpath(path)

        base_dir = self._base_dir or os.path.dirname(path)

        stack = Stack(is_nested=is_nested, name=name, assets=assets, origin_dir=os.path.dirname(path))

        template_dict = get_template_data(path)
        for key, value in template_dict.items():
            stack[key] = value

        resources_section = stack.get("Resources", DictSection())
        for resource in resources_section.section_items:
            resource_id = resource.item_id
            resource_type = resource.get("Type", None)
            properties = resource.get("Properties", {})
            package_type = properties.get("PackageType", ZIP)

            resource_assets = []

            if resource_type in NESTED_STACKS_RESOURCES:
                nested_stack = self.extract_nested_stack(path, resource_id, properties, resource_type)
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
            metadata_assets = []
            if metadata_type in METADATA_WITH_LOCAL_PATHS:
                for path_prop_name in METADATA_WITH_LOCAL_PATHS[metadata_type]:
                    asset_path = jmespath.search(path_prop_name, metadata_body)
                    asset = S3Asset(source_path=asset_path, source_property=path_prop_name)
                    metadata_assets.append(asset)
                    stack.assets.append(asset)

            metadata.assets = metadata_assets

        stack.extra_details[TEMPLATE_PATH_KEY] = path
        return stack

    def extract_nested_stack(self, parent_stack_template_path, resource_id, properties, resource_type) -> Stack:
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

    def write_project(self, project: Project, build_dir: str) -> None:
        for stack in project.stacks:
            _write_stack(stack, build_dir)

    def should_update_property_after_package(self, asset: Asset) -> bool:
        return True

    def update_resource_after_packaging(self, resource: Resource) -> None:
        pass

    def update_asset_params_default_values_after_packaging(self, stack: Stack, parameters: DictSection) -> None:
        pass


def _write_stack(stack: Stack, build_dir: str):
    stack_id = stack.stack_id or ""
    stack_build_location = os.path.join(build_dir, stack_id, "template.yaml")
    stack.extra_details[TEMPLATE_BUILD_PATH_KEY] = stack_build_location

    resources_section = stack.get("Resources", DictSection())
    for resource in resources_section.section_items:
        resource_type = resource.get("Type", None)
        if resource_type in NESTED_STACKS_RESOURCES and resource.nested_stack:
            nested_stack = resource.nested_stack
            _write_stack(nested_stack, os.path.dirname(stack_build_location))
            nested_stack_location_property_name = NESTED_STACKS_RESOURCES[resource_type]
            for asset in resource.assets:
                if isinstance(asset, S3Asset) and asset.source_property == nested_stack_location_property_name:
                    asset.updated_source_path = nested_stack.extra_details[TEMPLATE_BUILD_PATH_KEY]

    move_template(stack.extra_details[TEMPLATE_PATH_KEY], stack_build_location, stack)
