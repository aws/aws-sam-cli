"""
Provides the required classes and methods to handle CDK Cloud Assembly
"""
import os
import json
import copy
import logging
from typing import (
    Optional,
    Dict,
    List,
    Union,
)

from samcli.commands._utils.template import update_relative_paths, get_template_data
from samcli.lib.iac.cfn_iac import NESTED_STACKS_RESOURCES
from samcli.lib.utils.packagetype import IMAGE
from samcli.lib.samlib.resource_metadata_normalizer import (
    ASSET_PATH_METADATA_KEY,
    ASSET_PROPERTY_METADATA_KEY,
    METADATA_KEY,
)
from samcli.commands._utils.resources import AWS_CLOUDFORMATION_STACK, AWS_LAMBDA_FUNCTION
from samcli.lib.iac.cdk.helpers import (
    get_container_asset_id,
    get_nested_stack_asset_id,
)
from samcli.lib.iac.cdk.constants import (
    MANIFEST_FILENAME,
    TREE_FILENAME,
    OUT_FILENAME,
    STACK_TYPE,
    ASSET_TYPE,
    CDK_PATH_DELIMITER,
    CDK_PATH_METADATA_KEY,
)
from samcli.lib.iac.cdk.exceptions import (
    InvalidCloudAssemblyError,
)

LOG = logging.getLogger(__name__)


class CloudAssemblyTreeNode:
    """
    Class representing a cloud assembly tree node
    """

    RESOURCE_SUFFIX = "Resource"
    NESTED_STACK_SUFFIX = ".NestedStack"
    NESTED_STACK_RESOURCE_SUFFIX = ".NestedStackResource"

    def __init__(
        self,
        node_id: str,
        path: str,
        construct_info: Optional[Dict[str, str]] = None,
        children: Optional[Dict] = None,
        attributes: Optional[Dict] = None,
        parent: Optional["CloudAssemblyTreeNode"] = None,
    ):
        self._id = node_id
        self._path = path
        self._construct_info = construct_info if construct_info else {}
        self._children = children if children else {}
        self._attributes = attributes if attributes else {}
        self._parent = parent

    @property
    def id(self) -> str:
        return self._id

    @property
    def path(self) -> str:
        return self._path

    @property
    def construct_info(self) -> Dict[str, str]:
        return self._construct_info

    @property
    def _fqn(self) -> str:
        return self.construct_info["fqn"]

    @property
    def parent(self) -> Optional["CloudAssemblyTreeNode"]:
        return self._parent

    @property
    def children_map(self) -> Dict:
        return self._children

    @property
    def childrens(self) -> List["CloudAssemblyTreeNode"]:
        return list(self._children.values())

    def add_child(self, child_node: "CloudAssemblyTreeNode") -> None:
        child_id = child_node.id
        self._children[child_id] = child_node

    @property
    def attributes(self) -> Dict:
        return self._attributes

    def is_l1_construct(self) -> bool:
        """
        # e.g. @aws-cdk/aws-cloudformation.CfnStack
        """
        construct_name = self._fqn.split(".")[1]
        return construct_name.startswith("Cfn")

    def is_l2_construct_resource(self) -> bool:
        return self.is_l1_construct and self.id == CloudAssemblyTreeNode.RESOURCE_SUFFIX


class CloudAssemblyTree:
    """
    Class representing a cloud assembly tree

    A cloud assembly tree class wraps around the `tree.json` generated from `cdk synth`
    We use the tree mainly to retrieve a nested stack resource node
    """

    def __init__(self, tree_dict: Dict):
        self.root = CloudAssemblyTree._build_node(tree_dict["tree"])

    @staticmethod
    def _build_node(node_dict: Dict, parent: Optional[CloudAssemblyTreeNode] = None) -> CloudAssemblyTreeNode:
        node = CloudAssemblyTreeNode(
            node_id=node_dict["id"],
            path=node_dict["path"],
            attributes=node_dict.get("attributes", {}),
            construct_info=node_dict.get("constructInfo", {}),
            parent=parent,
        )
        for child_dict in node_dict.get("children", {}).values():
            child_node = CloudAssemblyTree._build_node(child_dict, node)
            node.add_child(child_node)
        return node

    def find_node_by_path(self, node_path: str) -> Optional[CloudAssemblyTreeNode]:
        """
        find and return node at given path

        Parameters:
        ----------
        node_path: str
            Path in leading to the node, e.g. RootStack/NestedStack/NestedNestedStack.NestedStackResource
        """
        if node_path.startswith(CDK_PATH_DELIMITER):
            # remove leading "/"
            node_path = node_path[1:]
        parts = node_path.split(CDK_PATH_DELIMITER)
        node = self.root
        for part in parts:
            if part in node.children_map:
                node = node.children_map[part]
            else:
                return None
        return node


class CloudAssemblyStack:
    """
    Represent a stack at root level in a Cloud Assembly
    For nested stack, use CloudAssemblyNestedStack

    Assets of a stack contains all assets (e.g. lambda code, nested stack template) at current level and also at
    nested stack levels
    """

    def __init__(
        self,
        stack_name: str,
        directory: str,
        source_directory: str,
        stack_artifact_dict: Optional[Dict] = None,
        assets_by_id: Optional[Dict] = None,
        assets_by_path: Optional[Dict] = None,
        skip_artifacts: bool = False,
    ):
        self._stack_name = stack_name
        self._stack_artifact_dict = stack_artifact_dict
        self._directory = directory
        self._source_directory = source_directory
        self._template = None
        self._assets_by_id = assets_by_id or {}
        self._assets_by_path = assets_by_path or {}
        self._nested_stacks_by_logical_id: Dict = {}
        self._nested_stacks_by_cdk_path: Dict = {}

        if not skip_artifacts:
            self._extract_assets()
        self._update_resources_paths()
        self._extract_nested_stacks()

    @property
    def stack_name(self) -> str:
        return self._stack_name

    @property
    def environment(self) -> str:
        env = self._stack_artifact_dict.get("environment")
        return env

    @property
    def account(self) -> str:
        return self.environment.split("/")[2:][0]

    @property
    def cdk_path(self) -> str:
        return self.stack_name

    @property
    def region(self) -> str:
        return self.environment.split("/")[2:][1]

    @property
    def directory(self) -> str:
        return self._directory

    @property
    def source_directory(self) -> str:
        return self._source_directory

    @property
    def template_file(self) -> str:
        return self._stack_artifact_dict.get("properties", {}).get("templateFile", f"{self.stack_name}.template.json")

    @property
    def template_full_path(self) -> str:
        return os.path.join(self._directory, self.template_file)

    @property
    def template(self) -> Dict:
        if self._template is not None:
            return self._template

        template_dict = get_template_data(self.template_full_path)

        # Add metadata for nested stack resource and for container function
        # Can remove this part once the metadata is added from CDK
        for resource in template_dict.get("Resources", {}).values():
            metadata = resource.get(METADATA_KEY, {})
            properties = resource.get("Properties", {})
            if resource.get("Type") == AWS_CLOUDFORMATION_STACK and metadata.get(CDK_PATH_METADATA_KEY):
                # nested stack asset
                asset_id = get_nested_stack_asset_id(resource)
                if asset_id is not None:
                    asset = self.find_asset_by_id(asset_id)
                    metadata[ASSET_PATH_METADATA_KEY] = asset["path"]
                    metadata[ASSET_PROPERTY_METADATA_KEY] = "TemplateURL"
            elif resource.get("Type") == AWS_LAMBDA_FUNCTION and properties.get("PackageType") == IMAGE:
                # container asset
                asset_id = get_container_asset_id(resource)
                if asset_id is not None:
                    asset = self.find_asset_by_id(asset_id)
                    if asset is not None:
                        metadata[ASSET_PATH_METADATA_KEY] = asset["path"]
                        metadata[ASSET_PROPERTY_METADATA_KEY] = "Code.ImageUri"

        self._template = template_dict
        return template_dict

    @property
    def metadata(self) -> Dict:
        return self._stack_artifact_dict.get("metadata", {})

    @property
    def assets(self) -> List[Dict]:
        return list(self._assets_by_id.values())

    @property
    def nested_stacks(self) -> List["CloudAssemblyNestedStack"]:
        return list(self._nested_stacks_by_logical_id.values())

    def find_asset_by_id(self, asset_id: str) -> Optional[Dict]:
        if asset_id in self._assets_by_id:
            return self._assets_by_id[asset_id]
        return None

    def find_asset_by_path(self, asset_path: str) -> Optional[Dict]:
        if asset_path in self._assets_by_path:
            return self._assets_by_path[asset_path]
        return None

    def find_nested_stack_by_logical_id(self, logical_id: str) -> "CloudAssemblyNestedStack":
        if logical_id in self._nested_stacks_by_logical_id:
            return self._nested_stacks_by_logical_id[logical_id]
        return None

    def find_nested_stack_by_cdk_path(self, cdk_path: str) -> Optional["CloudAssemblyNestedStack"]:
        if cdk_path in self._nested_stacks_by_cdk_path:
            return self._nested_stacks_by_cdk_path[cdk_path]
        return None

    def _extract_assets(self) -> None:
        for item in self.metadata.get(f"/{self.stack_name}", {}):
            assert "type" in item
            if item["type"] == ASSET_TYPE:
                self._assets_by_id[item["data"]["id"]] = item["data"]
                self._assets_by_path[item["data"]["path"]] = item["data"]

    def _update_resources_paths(self) -> None:
        update_relative_paths(self.template, self.source_directory, self.directory, skip_assets=True)

    def _move_explicit_assets(self) -> None:
        update_relative_paths(self.template, self.source_directory, self.directory, skip_assets=True)

    def find_metadata_by_type(self, type_: str) -> List[Dict]:
        metadata = []
        for key, item_list in self.metadata.items():
            for item in item_list:
                if item["type"] == type_:
                    item = copy.deepcopy(item)
                    item["path"] = key
                    metadata.append(item)
        return metadata

    def _extract_nested_stacks(self) -> None:
        """
        extract local nested stacks
        """
        resources = self.template.get("Resources", {})
        for logical_id, resource_dict in resources.items():
            type_ = resource_dict.get("Type")
            metadata = resource_dict.get(METADATA_KEY, {})
            if (
                type_ in NESTED_STACKS_RESOURCES
                and ASSET_PATH_METADATA_KEY in metadata
                and ASSET_PROPERTY_METADATA_KEY in metadata
                and CDK_PATH_METADATA_KEY in metadata
            ):
                # we only need local nested stacks
                nested_stack_name = os.path.basename(metadata[CDK_PATH_METADATA_KEY])[
                    : -len(CloudAssemblyTreeNode.NESTED_STACK_RESOURCE_SUFFIX)
                ]
                nested_stack = CloudAssemblyNestedStack(
                    parent=self,
                    template_file=metadata[ASSET_PATH_METADATA_KEY],
                    source_directory=self.source_directory,
                    logical_id=logical_id,
                    cdk_path=metadata[CDK_PATH_METADATA_KEY],
                    name=nested_stack_name,
                )

                self._nested_stacks_by_logical_id[logical_id] = nested_stack
                self._nested_stacks_by_cdk_path[metadata[CDK_PATH_METADATA_KEY]] = nested_stack
            # elif (
            #         type_ in NESTED_STACKS_RESOURCES
            #         and (
            #                 ASSET_PATH_METADATA_KEY not in metadata
            #                 or ASSET_PROPERTY_METADATA_KEY not in metadata
            #         )
            # ):
            #     nested_stack_path = resource_dict.get(PROPERTIES_KEY, {}).get(NESTED_STACKS_RESOURCES[type_])
            #     if not is_local_path(nested_stack_path):
            #         continue
            #     nested_stack_path = os.path.normpath(os.path.join(self.source_directory, nested_stack_path))
            #     cdk_path = metadata.get( CDK_PATH_METADATA_KEY, f"{self.cdk_path}/{logical_id}" )
            #     source_directory = os.path.dirname(nested_stack_path)
            #     nested_stack = CloudAssemblyNestedStack(
            #         parent=self,
            #         template_file=nested_stack_path,
            #         source_directory=source_directory,
            #         logical_id=logical_id,
            #         cdk_path=cdk_path,
            #         name=logical_id,
            #     )
            #     self._nested_stacks_by_logical_id[logical_id] = nested_stack
            #     self._nested_stacks_by_cdk_path[cdk_path] = nested_stack


class CloudAssemblyNestedStack(CloudAssemblyStack):
    def __init__(
        self,
        parent: CloudAssemblyStack,
        template_file: str,
        source_directory: str,
        logical_id: str,
        name: str,
        cdk_path: str,
    ):
        self._parent = parent
        self._logical_id = logical_id
        self._cdk_path = cdk_path
        self._template_file = template_file
        super().__init__(
            stack_name=name,
            directory=parent.directory,
            source_directory=source_directory,
            assets_by_id=parent._assets_by_id,
            assets_by_path=parent._assets_by_path,
            skip_artifacts=True,
        )

    @property
    def cdk_path(self) -> str:
        return self._cdk_path

    @property
    def environment(self) -> str:
        return self.parent.environment

    @property
    def account(self) -> str:
        return self.parent.account

    @property
    def region(self) -> str:
        return self.parent.region

    @property
    def template_file(self) -> str:
        return self._template_file

    @property
    def template_full_path(self) -> str:
        return os.path.join(self.directory, self.template_file)

    @property
    def parent(self) -> Union[CloudAssemblyStack, "CloudAssemblyNestedStack"]:
        return self._parent


def _validate_cloud_assembly(directory: str) -> None:
    """
    Validate if the provided dir contains a cloud assembly
    (i.e. manifest.json, tree.json and cdk.out)
    """
    LOG.debug("_validate_cloud_assembly: %s", directory)
    missing_files = []
    for filename in [MANIFEST_FILENAME, TREE_FILENAME, OUT_FILENAME]:
        if not os.path.exists(os.path.join(directory, filename)):
            missing_files.append(filename)
    if missing_files:
        raise InvalidCloudAssemblyError(missing_files=missing_files)


class CloudAssembly:
    def __init__(self, cloud_assembly_directory: str, source_directory: str):
        self._directory = cloud_assembly_directory
        self._source_directory = source_directory
        self._manifest_dict = None
        self._tree = None
        self._stacks: Dict[str, CloudAssemblyStack] = {}

        _validate_cloud_assembly(cloud_assembly_directory)
        self._read_manifest()
        self._build_tree()
        self._build_stacks()

    @property
    def directory(self) -> str:
        return self._directory

    @property
    def version(self) -> str:
        return self._manifest_dict["version"]

    @property
    def tree(self) -> CloudAssemblyTree:
        if self._tree is None:
            self._build_tree()
        return self._tree

    @property
    def artifacts(self) -> Dict:
        return self._manifest_dict.get("artifacts", {})

    @property
    def tree_filename(self) -> str:
        return self.artifacts.get("Tree", {}).get("properties", {}).get("file", TREE_FILENAME) or TREE_FILENAME

    @property
    def stacks(self) -> List[CloudAssemblyStack]:
        return list(self._stacks.values())

    def find_stack_by_stack_name(self, stack_name: str) -> Optional[CloudAssemblyStack]:
        if stack_name in self._stacks:
            return self._stacks[stack_name]
        return None

    def _read_manifest(self) -> None:
        with open(os.path.join(self._directory, MANIFEST_FILENAME), "r") as f:
            manifest_dict = json.loads(f.read())
        self._manifest_dict = manifest_dict

    def _build_tree(self) -> None:
        with open(os.path.join(self._directory, self.tree_filename), "r") as f:
            tree_dict = json.loads(f.read())
        self._tree = CloudAssemblyTree(tree_dict)

    def _build_stacks(self) -> None:
        self._stacks = {}
        for key, item in self.artifacts.items():
            if item["type"] == STACK_TYPE:
                self._stacks[key] = CloudAssemblyStack(
                    stack_name=key,
                    stack_artifact_dict=item,
                    directory=self._directory,
                    source_directory=self._source_directory,
                )
