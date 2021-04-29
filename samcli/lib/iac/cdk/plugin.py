"""
Provide CDK IAC implementations
"""
import os
import copy
import json
import shutil
import subprocess
import logging
import platform
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import (
    Dict,
    List,
    Union,
    Optional,
)
from _collections_abc import Mapping

from samcli.lib.iac.cdk.constants import (
    MANIFEST_FILENAME,
    OUT_FILENAME,
    TREE_FILENAME,
    FILE_ASSET_PACKAGING,
    ZIP_ASSET_PACKAGING,
    CONTAINER_IMAGE_ASSET_PACKAGING,
)
from samcli.lib.iac.cfn_iac import NESTED_STACKS_RESOURCES
from samcli.commands._utils.template import TemplateFormat, move_template
from samcli.lib.iac.interface import (
    DictSection,
    IacPlugin,
    Project,
    LookupPath,
    LookupPathType,
    DictSectionItem,
    Resource,
    Parameter,
    Stack,
    S3Asset,
    ImageAsset,
    SimpleSection,
    Asset,
)
from samcli.lib.iac.cdk.cloud_assembly import (
    CDK_PATH_METADATA_KEY,
    CloudAssembly,
    CloudAssemblyNestedStack,
    CloudAssemblyStack,
)
from samcli.lib.iac.cdk.exceptions import (
    CdkSynthError,
    CdkToolkitNotInstalledError,
    CdkPluginError,
    InvalidCloudAssemblyError,
)
from samcli.cli.context import Context
from samcli.lib.samlib.resource_metadata_normalizer import (
    METADATA_KEY,
    ASSET_PATH_METADATA_KEY,
    ASSET_PROPERTY_METADATA_KEY,
    ResourceMetadataNormalizer,
    ASSET_LOCAL_IMAGE_METADATA_KEY,
)

TEMP_CDK_OUT = ".aws-sam/.cdk-out"

LOG = logging.getLogger(__name__)

CDK_CONFIG_FILENAME = "cdk.json"
STACK_EXTRA_DETAILS_TEMPLATE_FILENAME_KEY = "template_file"
RESOURCE_EXTRA_DETAILS_ORIGINAL_BODY_KEY = "original_body"


class CdkPlugin(IacPlugin):
    """
    CDK Plugin
    """

    def __init__(self, context: Context):
        super().__init__(context=context)
        # create a temp dir to hold synthed/read Cloud Assembly
        # will remove the temp dir once the command exits
        self._source_dir = os.path.abspath(os.curdir)
        Path(TEMP_CDK_OUT).mkdir(parents=True, exist_ok=True)
        self._cloud_assembly_dir = TEMP_CDK_OUT

    def get_project(self, lookup_paths: List[LookupPath]) -> Project:
        """
        Read and parse template of that IaC Platform
        """
        cdk_app = self._context.command_params.get("cdk_app")
        is_cloud_assembly_dir = bool(cdk_app) and os.path.isfile(os.path.join(cdk_app, MANIFEST_FILENAME))
        cdk_context = self._context.command_params.get("cdk_context")
        cloud_assembly_dir = None
        missing_files: List = []
        for lookup_path in lookup_paths:
            if lookup_path.lookup_path_type == LookupPathType.BUILD:
                cloud_assembly_dir = os.path.abspath(lookup_path.lookup_path_dir)
                missing_files = []
                for filename in [MANIFEST_FILENAME, TREE_FILENAME, OUT_FILENAME]:
                    if not os.path.exists(os.path.join(cloud_assembly_dir, filename)):
                        missing_files.append(filename)
                if not missing_files and cloud_assembly_dir:
                    self._source_dir = cloud_assembly_dir
                    break
            else:
                cloud_assembly_dir = self._cdk_synth(app=cdk_app, context=cdk_context)
                if is_cloud_assembly_dir:
                    cloud_assembly_dir = os.path.abspath(cdk_app)
                    self._source_dir = cloud_assembly_dir or ""
                break
        if not cloud_assembly_dir:
            raise InvalidCloudAssemblyError(missing_files)
        project = self._get_project_from_cloud_assembly(cloud_assembly_dir)
        return project

    def write_project(self, project: Project, build_dir: str) -> None:
        """
        Write project to a template (or a set of templates),
        move the template(s) to build_path
        """
        for filename in [MANIFEST_FILENAME, TREE_FILENAME, OUT_FILENAME]:
            shutil.copy2(os.path.join(self._cloud_assembly_dir, filename), os.path.join(build_dir, filename))

        _update_built_artifacts(project, self._cloud_assembly_dir, build_dir)

        for stack in project.stacks:
            _write_stack(stack, self._cloud_assembly_dir, build_dir)

        # p = subprocess.run(["tree", build_dir], capture_output=True)
        # LOG.info(p)

    def _cdk_synth(self, app: Optional[str] = None, context: Optional[List] = None) -> str:
        """
        Run cdk synth to get the cloud assembly
        """
        context = context or []
        cdk_executable = self._cdk_executable_path
        LOG.debug("CDK Toolkit found at %s", cdk_executable)
        synth_command = [
            cdk_executable,
            "synth",
            "--no-staging",
        ]
        if app is not None:
            synth_command.append("--app")
            synth_command.append(app)

        if (app is None) or (app is not None and not os.path.isdir(app)):
            synth_command.append("-o")
            synth_command.append(self._cloud_assembly_dir)

        if context is not None:
            for keyvalpair in context:
                synth_command.append("--context")
                synth_command.append(keyvalpair)

        try:
            LOG.info("Synthesizing CDK App")
            LOG.debug("command: %s", synth_command)
            subprocess.check_output(
                synth_command,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as cdk_error:
            output = cdk_error.output.decode("utf-8")
            raise CdkSynthError(output) from cdk_error

        if app is not None and os.path.isdir(app):
            copy_tree(app, self._cloud_assembly_dir)

        LOG.debug("Cloud assembly synthed at %s", self._cloud_assembly_dir)
        return self._cloud_assembly_dir

    @property
    def _cdk_executable_path(self) -> str:
        """
        Order to look up locally installed CDK Toolkit
        1. ./node_modules/aws-cdk/bin/cdk (for mac & linux only)
        2. cdk
        """
        if platform.system().lower() == "windows":
            cdk_executables = ["cdk"]
        else:
            cdk_executables = [
                "./node_modules/aws-cdk/bin/cdk",
                "cdk",
            ]

        for executable in cdk_executables:
            # check if exists and is executable
            full_executable = shutil.which(executable)
            if full_executable:
                return full_executable
        raise CdkToolkitNotInstalledError(
            "CDK Toolkit is not found or not installed. Please run `npm i -g aws-cdk@latest` to install the latest CDK "
            "Toolkit."
        )

    def _get_project_from_cloud_assembly(self, cloud_assembly_dir: str) -> Project:
        """
        create a cdk project from cloud_assembly
        """
        cloud_assembly = CloudAssembly(cloud_assembly_dir, self._source_dir)
        stacks: List[Stack] = [self._build_stack(cloud_assembly, ca_stack) for ca_stack in cloud_assembly.stacks]
        project = Project(stacks=stacks)
        return project

    def _build_stack(
        self, cloud_assembly: CloudAssembly, ca_stack: Union[CloudAssemblyStack, CloudAssemblyNestedStack]
    ) -> Stack:
        """
        Extract stack from given CloudAssemblyStack
        """
        assets = _collect_assets(ca_stack)
        sections = {}
        for section_key, section_dict in ca_stack.template.items():
            if section_key == "Resources":
                section = DictSection(section_key)
                self._build_resources_section(assets, ca_stack, cloud_assembly, section, section_dict)
            elif section_key == "Parameters":
                section = DictSection(section_key)
                for logical_id, param_dict in section_dict.items():
                    param = Parameter(
                        key=logical_id,
                        body=param_dict,
                    )
                    section[logical_id] = param
            elif isinstance(section_dict, Mapping):
                section = DictSection(section_key)
                for logical_id, section_item_dict in section_dict.items():
                    section_item = DictSectionItem(
                        key=logical_id,
                        body=section_item_dict,
                    )
                    section[logical_id] = section_item
            else:
                section = SimpleSection(section_key, section_dict)
            sections[section_key] = section

        LOG.debug("ca-stack_name: %s", ca_stack.stack_name)
        return Stack(
            stack_id=ca_stack.stack_name,
            name=ca_stack.stack_name,
            is_nested=isinstance(ca_stack, CloudAssemblyNestedStack),
            sections=sections,
            assets=list(assets.values()),
            origin_dir=os.path.dirname(ca_stack.template_full_path),
            extra_details={STACK_EXTRA_DETAILS_TEMPLATE_FILENAME_KEY: os.path.split(ca_stack.template_file)[1]},
        )

    def _build_resources_section(
        self,
        assets: Dict[str, Union[S3Asset, ImageAsset]],
        ca_stack: Union[CloudAssemblyStack, CloudAssemblyNestedStack],
        cloud_assembly: CloudAssembly,
        section: DictSection,
        section_dict: Dict,
    ) -> None:
        for logical_id, resource_dict in section_dict.items():
            resource_type = resource_dict["Type"]
            metadata = resource_dict.get("Metadata", {})
            cdk_path = metadata.get(CDK_PATH_METADATA_KEY, None)
            tree_node = cloud_assembly.tree.find_node_by_path(cdk_path) if cdk_path else None
            if tree_node and tree_node.is_l2_construct_resource():
                tree_node = tree_node.parent

            resource = Resource(
                key=logical_id,
                body=resource_dict,
                item_id=logical_id if not tree_node else tree_node.id,
            )

            if ASSET_PATH_METADATA_KEY in metadata and ASSET_PROPERTY_METADATA_KEY in metadata:
                # hook up asset
                asset_path = metadata[ASSET_PATH_METADATA_KEY]
                asset_property = metadata[ASSET_PROPERTY_METADATA_KEY]
                asset = assets[asset_path]
                asset.source_property = asset_property
                if isinstance(asset, ImageAsset) and ASSET_LOCAL_IMAGE_METADATA_KEY in metadata:
                    asset.source_local_image = metadata[ASSET_LOCAL_IMAGE_METADATA_KEY]
                resource.assets = resource.assets or []
                resource.assets.append(asset)
                # we also need to "normalize" metadata,
                # and keep an original copy for writing the project to template(s)
                original_body = copy.deepcopy(resource_dict)
                resource.extra_details[RESOURCE_EXTRA_DETAILS_ORIGINAL_BODY_KEY] = original_body
                ResourceMetadataNormalizer.replace_property(asset_property, asset_path, resource, logical_id)

            if resource_type in NESTED_STACKS_RESOURCES:
                # hook up and extract nested stacks
                ca_nested_stack = ca_stack.find_nested_stack_by_logical_id(logical_id)
                if ca_nested_stack is not None:
                    nested_stack = self._build_stack(cloud_assembly, ca_nested_stack)
                    resource.nested_stack = nested_stack
                    if not resource.assets:
                        resource.assets = [
                            S3Asset(
                                source_path=ca_nested_stack.template_full_path,
                                source_property=NESTED_STACKS_RESOURCES[resource_type],
                            )
                        ]
            section[logical_id] = resource


def _get_app_executable_path_from_config() -> str:
    with open(CDK_CONFIG_FILENAME, "r") as f:
        app_json = json.loads(f.read())
        app: str = app_json.get("app")
    if app is None:
        raise CdkPluginError(f"'app' is missing in {CDK_CONFIG_FILENAME}")
    return app


def _collect_assets(
    ca_stack: Union[CloudAssemblyStack, CloudAssemblyNestedStack]
) -> Dict[str, Union[S3Asset, ImageAsset]]:
    assets: Dict[str, Union[S3Asset, ImageAsset]] = {}
    for ca_asset in ca_stack.assets:
        if ca_asset["path"] not in assets:
            if ca_asset["packaging"] in [ZIP_ASSET_PACKAGING, FILE_ASSET_PACKAGING]:
                path = os.path.normpath(os.path.join(ca_stack.directory, ca_asset["path"]))
                assets[ca_asset["path"]] = S3Asset(asset_id=ca_asset["id"], source_path=path)
            elif ca_asset["packaging"] == CONTAINER_IMAGE_ASSET_PACKAGING:
                path = os.path.normpath(os.path.join(ca_stack.directory, ca_asset["path"]))
                repository_name = ca_asset.get("repositoryName", None)
                registry_name = None
                if repository_name:
                    repository_name, registry_name = repository_name.split("/")
                assets[ca_asset["path"]] = ImageAsset(
                    asset_id=ca_asset["id"],
                    source_path=path,
                    repository_name=repository_name,
                    registry=registry_name,
                    target=ca_asset.get("target", None),
                    image_tag=ca_asset.get("imageTag", None),
                    docker_file_name=ca_asset.get("file", None) or "Dockerfile",
                    build_args=ca_asset.get("buildArgs", None),
                )
    return assets


def _write_stack(stack: Stack, cloud_assembly_dir: str, build_dir: str) -> None:
    # write template
    src_template_path = os.path.join(stack.origin_dir, stack.extra_details[STACK_EXTRA_DETAILS_TEMPLATE_FILENAME_KEY])
    stack_build_location = os.path.join(build_dir, stack.extra_details[STACK_EXTRA_DETAILS_TEMPLATE_FILENAME_KEY])

    resources = stack.get("Resources", {})
    for _, resource in resources.items():
        if RESOURCE_EXTRA_DETAILS_ORIGINAL_BODY_KEY in resource.extra_details:
            for key, val in resource.extra_details[RESOURCE_EXTRA_DETAILS_ORIGINAL_BODY_KEY].items():
                resource[key] = val
        if resource.assets:
            asset = resource.assets[0]
            if isinstance(asset, ImageAsset) and asset.source_local_image is not None:
                resource[METADATA_KEY][ASSET_LOCAL_IMAGE_METADATA_KEY] = asset.source_local_image
            elif isinstance(asset, S3Asset) and ASSET_PATH_METADATA_KEY in resource.get(METADATA_KEY, {}):
                updated_path = asset.updated_source_path or asset.source_path
                resource[METADATA_KEY][ASSET_PATH_METADATA_KEY] = updated_path
        if resource.nested_stack:
            _write_stack(resource.nested_stack, cloud_assembly_dir, build_dir)
            for asset in resource.assets:
                if isinstance(asset, S3Asset) and asset.source_property in NESTED_STACKS_RESOURCES.values():
                    nested_stack_file_name = resource.nested_stack.extra_details[
                        STACK_EXTRA_DETAILS_TEMPLATE_FILENAME_KEY
                    ]
                    asset.updated_source_path = os.path.join(build_dir, nested_stack_file_name)
                    resource[METADATA_KEY][ASSET_PATH_METADATA_KEY] = updated_path
    move_template(src_template_path, stack_build_location, stack, output_format=TemplateFormat.JSON)


def _collect_stack_assets(stack: Stack) -> Dict[str, Asset]:
    collected_assets: Dict[str, Asset] = {}
    sections: Dict = stack.sections or {}
    for _, section in sections.items():
        if not isinstance(section, DictSection):
            continue
        for section_item in section.section_items:
            assets = section_item.assets or []
            for asset in assets:
                collected_assets[asset.asset_id] = asset
            if not isinstance(section_item, Resource) or not section_item.nested_stack:
                continue

            nested_stack_assets = _collect_stack_assets(section_item.nested_stack)
            for asset_id, asset in nested_stack_assets.items():
                if asset_id in collected_assets:
                    _shallow_clone_asset(asset, asset_id, collected_assets)
                else:
                    collected_assets[asset_id] = asset

    return collected_assets


def _shallow_clone_asset(asset, asset_id, collected_assets):
    if isinstance(asset, S3Asset):
        asset.updated_source_path = collected_assets[asset_id].updated_source_path
        asset.source_property = collected_assets[asset_id].source_property
        asset.source_path = collected_assets[asset_id].source_path
        asset.destinations = collected_assets[asset_id].destinations
        asset.object_version = collected_assets[asset_id].object_version
        asset.object_key = collected_assets[asset_id].object_key
        asset.bucket_name = collected_assets[asset_id].bucket_name
    elif isinstance(asset, ImageAsset):
        asset.source_local_image = collected_assets[asset_id].source_local_image
        asset.target = collected_assets[asset_id].target
        asset.build_args = collected_assets[asset_id].build_args
        asset.docker_file_name = collected_assets[asset_id].docker_file_name
        asset.image_tag = collected_assets[asset_id].image_tag
        asset.registry = collected_assets[asset_id].registry
        asset.repository_name = collected_assets[asset_id].repository_name


def _update_built_artifacts(project: Project, cloud_assembly_dir: str, build_dir: str) -> None:
    with open(os.path.join(build_dir, MANIFEST_FILENAME), "r") as f:
        manifest_dict = json.loads(f.read())

    assets, root_stack_names = _collect_project_assets(project)

    for artifact_name, artifact in manifest_dict.get("artifacts", {}).items():
        if artifact_name not in root_stack_names:
            continue
        metadata = artifact.get("metadata", {})
        stack_metadata_items = metadata.get(f"/{artifact_name}", [])
        stack_assets = assets.get(artifact_name, {})
        for item in stack_metadata_items:
            if item.get("type", None) != "aws:cdk:asset":
                continue
            asset_data = item.get("data", {})

            if asset_data["id"] not in stack_assets:
                continue

            if asset_data.get("packaging", None) == "zip":
                stack_asset = stack_assets[asset_data["id"]]
                updated_path = stack_asset.updated_source_path or stack_asset.source_path

                asset_data["path"] = updated_path
                item["data"] = asset_data

    with open(os.path.join(build_dir, MANIFEST_FILENAME), "w") as f:
        f.write(json.dumps(manifest_dict, indent=4))


def _collect_project_assets(project):
    assets: Dict[str, Asset] = {}
    root_stack_names = []
    for stack in project.stacks:
        assets[stack.name] = _collect_stack_assets(stack)
        root_stack_names.append(stack.name)
    return assets, root_stack_names
