"""
Cloud Formation IaC plugin implementation
"""
import os
from typing import List, Optional
from urllib.parse import unquote, urlparse

import jmespath

from samcli.cli.context import Context
from samcli.commands._utils.resources import RESOURCES_WITH_LOCAL_PATHS
from samcli.lib.iac.interface import IacPlugin, Project, LookupPath, Stack, DictSection, S3Asset, Asset
from samcli.commands._utils.template import get_template_data, move_template
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider, is_local_path, get_local_path

PARENT_STACK_TEMPLATE_PATH_KEY = "parent_stack_template_path"
TEMPLATE_PATH_KEY = "template_path"
TEMPLATE_BUILD_PATH_KEY = "template_build_path"

NESTED_STACKS_RESOURCES = {
    SamLocalStackProvider.SERVERLESS_APPLICATION: "Location",
    SamLocalStackProvider.CLOUDFORMATION_STACK: "TemplateURL",
}

BASE_DIR_RESOURCES = [
    SamLocalStackProvider.SERVERLESS_FUNCTION,
    SamLocalStackProvider.LAMBDA_FUNCTION,
    SamLocalStackProvider.SERVERLESS_LAYER,
    SamLocalStackProvider.LAMBDA_LAYER,
]


class CfnIacPlugin(IacPlugin):
    def __init__(self, context: Context):
        self._template_file = context.command_params["template_file"]
        self._base_dir = context.command_params.get("base_dir", None)
        super().__init__(context)

    def get_project(self, lookup_paths: List[LookupPath]) -> Project:
        stacks = [self._build_stack(self._template_file)]

        return Project(stacks)

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

            resource_assets = []

            if resource_type in NESTED_STACKS_RESOURCES:
                nested_stack = self.extract_nested_stack(path, resource_id, properties, resource_type)
                resource.nested_stack = nested_stack

            if resource_type in RESOURCES_WITH_LOCAL_PATHS:
                for path_prop_name in RESOURCES_WITH_LOCAL_PATHS[resource_type]:
                    asset_path = jmespath.search(path_prop_name, properties)
                    if is_local_path(asset_path):
                        reference_path = base_dir if resource_type in BASE_DIR_RESOURCES else os.path.dirname(path)
                        asset_path = get_local_path(asset_path, reference_path)
                        asset = S3Asset(source_path=asset_path, source_property=path_prop_name)
                        resource_assets.append(asset)

            resource.assets = resource_assets

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
