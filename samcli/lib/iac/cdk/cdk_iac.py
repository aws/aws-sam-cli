"""
Provide a CDK implementation of IaCPluginInterface
"""

# pylint: skip-file
import copy
import logging
import os
import platform
import shutil
import subprocess
from distutils.dir_util import copy_tree
from pathlib import Path
from typing import List, Optional, Dict, Union, Mapping

from samcli.commands._utils.resources import NESTED_STACKS_RESOURCES
from samcli.lib.iac.cdk.cloud_assembly import CloudAssembly, CloudAssemblyStack, CloudAssemblyNestedStack
from samcli.lib.iac.cdk.constants import (
    MANIFEST_FILENAME,
    TREE_FILENAME,
    OUT_FILENAME,
    CDK_PATH_METADATA_KEY,
    ZIP_ASSET_PACKAGING,
    FILE_ASSET_PACKAGING,
    CONTAINER_IMAGE_ASSET_PACKAGING,
)
from samcli.lib.iac.cdk.exceptions import InvalidCloudAssemblyError, CdkToolkitNotInstalledError, CdkSynthError
from samcli.lib.iac.cdk.plugin import (
    TEMP_CDK_OUT,
    RESOURCE_EXTRA_DETAILS_ORIGINAL_BODY_KEY,
    STACK_EXTRA_DETAILS_TEMPLATE_FILENAME_KEY,
)
from samcli.lib.iac.constants import PARAMETER_OVERRIDES, GLOBAL_PARAMETER_OVERRIDES
from samcli.lib.iac.plugins_interfaces import (
    IaCPluginInterface,
    SamCliProject,
    Stack,
    SamCliContext,
    LookupPathType,
    Resource,
    ImageAsset,
    S3Asset,
    DictSection,
    SimpleSection,
    DictSectionItem,
    Parameter,
    LookupPath,
)
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.samlib.resource_metadata_normalizer import (
    ASSET_PATH_METADATA_KEY,
    ASSET_PROPERTY_METADATA_KEY,
    ASSET_LOCAL_IMAGE_METADATA_KEY,
    ResourceMetadataNormalizer,
)

LOG = logging.getLogger(__name__)


# TODO: Implement the new interface methods for the CDK plugin type
class CdkIacImplementation(IaCPluginInterface):
    """
    CDK implementation for the plugins interface.
    read_project parses the CDK and returns a SamCliProject object
    write_project writes the updated project
        back to the build dir and returns true if successful
    update_packaged_locations updates the package locations and r
        returns true if successful
    get_iac_file_types returns a list of file types/patterns associated with
        the CDK project type
    """

    def __init__(self, context: SamCliContext):
        super().__init__(context)
        # create a temp dir to hold synthed/read Cloud Assembly
        # will remove the temp dir once the command exits
        self._source_dir = os.path.abspath(os.curdir)
        Path(TEMP_CDK_OUT).mkdir(parents=True, exist_ok=True)
        self._cloud_assembly_dir = TEMP_CDK_OUT

    def read_project(self, lookup_paths: List[LookupPath]) -> SamCliProject:
        command_options = self._context.command_options_map
        cdk_app = command_options.get("cdk_app")
        is_cloud_assembly_dir = bool(cdk_app) and os.path.isfile(os.path.join(cdk_app, MANIFEST_FILENAME))
        cdk_context = command_options.get("cdk_context")
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

    def write_project(self, project: SamCliProject, build_dir: str) -> bool:
        pass

    def update_packaged_locations(self, stack: Stack) -> bool:
        pass

    @staticmethod
    def get_iac_file_patterns() -> List[str]:
        return ["cdk.json"]

    def _cdk_synth(self, app: Optional[str] = None, context: Optional[List] = None) -> str:
        """
        Run cdk synth to get the cloud assembly
        """
        context = context or []
        cdk_executable = _get_cdk_executable_path()
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

    def _get_project_from_cloud_assembly(self, cloud_assembly_dir: str) -> SamCliProject:
        """
        create a cdk project from cloud_assembly
        """
        cloud_assembly = CloudAssembly(cloud_assembly_dir, self._source_dir)
        stacks: List[Stack] = [self._build_stack(cloud_assembly, ca_stack) for ca_stack in cloud_assembly.stacks]
        project = SamCliProject(stacks=stacks)
        return project

    def _build_stack(
        self, cloud_assembly: CloudAssembly, ca_stack: Union[CloudAssemblyStack, CloudAssemblyNestedStack]
    ) -> Stack:
        """
        Extract stack from given CloudAssemblyStack
        """
        assets = _collect_assets(ca_stack)
        LOG.debug("Found assets: %s", str(assets))
        asset_parameters = {
            asset_param
            for asset in assets.values()
            for asset_param in asset.extra_details.get("assetParameters", {}).values()
        }
        sections = {}
        options_map = self._context.command_options_map
        template = SamBaseProvider.get_resolved_template_dict(
            ca_stack.template,
            SamLocalStackProvider.merge_parameter_overrides(
                options_map.get(PARAMETER_OVERRIDES), options_map.get(GLOBAL_PARAMETER_OVERRIDES)
            ),
            normalize_resource_metadata=False,
        )
        for section_key, section_dict in template.items():
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
                    if logical_id in asset_parameters:
                        param.added_by_iac = True
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
                if ASSET_LOCAL_IMAGE_METADATA_KEY in metadata:
                    ResourceMetadataNormalizer.replace_property(
                        asset_property, metadata[ASSET_LOCAL_IMAGE_METADATA_KEY], resource, logical_id
                    )
                else:
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


def _collect_assets(
    ca_stack: Union[CloudAssemblyStack, CloudAssemblyNestedStack]
) -> Dict[str, Union[S3Asset, ImageAsset]]:
    assets: Dict[str, Union[S3Asset, ImageAsset]] = {}
    for ca_asset in ca_stack.assets:
        if ca_asset["path"] not in assets:
            if ca_asset["packaging"] in [ZIP_ASSET_PACKAGING, FILE_ASSET_PACKAGING]:
                path = os.path.normpath(os.path.join(ca_stack.directory, ca_asset["path"]))
                extra_details = {
                    "assetParameters": {
                        "s3BucketParameter": ca_asset["s3BucketParameter"],
                        "s3KeyParameter": ca_asset["s3KeyParameter"],
                        "artifactHashParameter": ca_asset["artifactHashParameter"],
                    }
                }
                assets[ca_asset["path"]] = S3Asset(
                    asset_id=ca_asset["id"], source_path=path, extra_details=extra_details
                )
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


def _get_cdk_executable_path() -> str:
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
