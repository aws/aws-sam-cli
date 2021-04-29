import collections
import json
import os
from collections import OrderedDict
from unittest import TestCase
from unittest.mock import patch

from samcli.lib.iac.cdk.cloud_assembly import (
    CloudAssembly,
    CloudAssemblyNestedStack,
    CloudAssemblyStack,
    CloudAssemblyTree,
    CloudAssemblyTreeNode,
)
from tests.unit.lib.iac.cdk.helper import read_json_file

CLOUD_ASSEMBLY_DIR = os.path.join(os.path.dirname(__file__), "test_data", "cdk.out")
SOURCE_DIR = os.path.join(os.path.dirname(__file__), "test_data", "cdk.out")


class TestCloudAssembly(TestCase):
    def setUp(self) -> None:
        self.cloud_assembly = CloudAssembly(CLOUD_ASSEMBLY_DIR, SOURCE_DIR)

    def test_version(self):
        self.assertEqual(self.cloud_assembly.version, "9.0.0")

    def test_tree(self):
        self.assertIsInstance(self.cloud_assembly.tree, CloudAssemblyTree)

    def test_artifacts(self):
        with open(os.path.join(CLOUD_ASSEMBLY_DIR, "manifest.json"), "r") as f:
            manifest_dict = json.loads(f.read())
        artifact_dict = manifest_dict["artifacts"]
        self.assertEqual(self.cloud_assembly.artifacts, artifact_dict)

    def test_tree_filename(self):
        self.assertEqual(self.cloud_assembly.tree_filename, "tree.json")

    def test_stacks(self):
        stacks = self.cloud_assembly.stacks
        self.assertEqual(len(stacks), 2)
        for stack in stacks:
            self.assertIsInstance(stack, CloudAssemblyStack)

    def test_find_stack_by_stack_name_exisit(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertIsInstance(stack, CloudAssemblyStack)

    def test_find_stack_by_stack_name_none(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("other-stack")
        self.assertIsNone(stack)


class TestCloudAssemblyStack(TestCase):
    def setUp(self) -> None:
        self.cloud_assembly = CloudAssembly(CLOUD_ASSEMBLY_DIR, SOURCE_DIR)

    def test_stack_name(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.stack_name, "root-stack")

    def test_environment(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.environment, "aws://unknown-account/unknown-region")

    def test_account(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.account, "unknown-account")

    def test_region(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.region, "unknown-region")

    def test_directory(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.directory, CLOUD_ASSEMBLY_DIR)

    def test_template_file(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.template_file, "root-stack.template.json")

    def test_template_full_path(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertEqual(stack.template_full_path, os.path.join(CLOUD_ASSEMBLY_DIR, "root-stack.template.json"))

    def test_template(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        expected = read_json_file(
            os.path.join(CLOUD_ASSEMBLY_DIR, "root-stack.template.normalized.json"), "<current_dir_path>/", ""
        )
        self.assertDictEqual(stack.template, expected)

    def test_assets(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        assets = stack.assets
        self.assertIsInstance(assets, list)
        self.assertEqual(len(assets), 5)

    def test_find_asset_by_id(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        asset = stack.find_asset_by_id("8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e")
        expected = {
            "repositoryName": "aws-cdk/assets",
            "imageTag": "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
            "id": "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
            "packaging": "container-image",
            "path": "asset.8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
            "sourceHash": "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e",
        }
        self.assertEqual(asset, expected)

    def test_find_asset_by_path(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        asset = stack.find_asset_by_path("asset.97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e")
        expected = {
            "path": "asset.97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e",
            "id": "97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e",
            "packaging": "zip",
            "sourceHash": "97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0e",
            "s3BucketParameter": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3BucketDD3A7E9A",
            "s3KeyParameter": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3VersionKeyCEC49660",
            "artifactHashParameter": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eArtifactHashBD7218A6",
        }
        self.assertEqual(asset, expected)

    def test_nested_stacks(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        nested_stacks = stack.nested_stacks
        self.assertIsInstance(nested_stacks, list)
        self.assertEqual(len(nested_stacks), 1)
        self.assertIsInstance(nested_stacks[0], CloudAssemblyNestedStack)

    def test_find_nested_stack_by_logical_id(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        nested_stack = stack.find_nested_stack_by_logical_id(
            "nestedstackNestedStacknestedstackNestedStackResource71CDD241"
        )
        self.assertIsInstance(nested_stack, CloudAssemblyNestedStack)

    def test_find_nested_stack_by_cdk_path(self):
        stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        nested_stack = stack.find_nested_stack_by_cdk_path(
            "root-stack/nested-stack.NestedStack/nested-stack.NestedStackResource"
        )
        self.assertIsInstance(nested_stack, CloudAssemblyNestedStack)


class TestCloudAssemblyNestedStack(TestCase):
    def setUp(self) -> None:
        self.cloud_assembly = CloudAssembly(CLOUD_ASSEMBLY_DIR, SOURCE_DIR)
        self.stack = self.cloud_assembly.find_stack_by_stack_name("root-stack")
        self.assertIsNotNone(self.stack)
        if self.stack:
            self.nested_stack = self.stack.find_nested_stack_by_cdk_path(
                "root-stack/nested-stack.NestedStack/nested-stack.NestedStackResource"
            )

    def test_stack_name(self):
        self.assertEqual(self.nested_stack.stack_name, "nested-stack")

    def test_environment(self):
        self.assertEqual(self.nested_stack.environment, "aws://unknown-account/unknown-region")

    def test_account(self):
        self.assertEqual(self.nested_stack.account, "unknown-account")

    def test_region(self):
        self.assertEqual(self.nested_stack.region, "unknown-region")

    def test_directory(self):
        self.assertEqual(self.nested_stack.directory, CLOUD_ASSEMBLY_DIR)

    def test_template_file(self):
        self.assertEqual(self.nested_stack.template_file, "rootstacknestedstackACD02B51.nested.template.json")

    def test_template_full_path(self):
        self.assertEqual(
            self.nested_stack.template_full_path,
            os.path.join(CLOUD_ASSEMBLY_DIR, "rootstacknestedstackACD02B51.nested.template.json"),
        )

    def test_template(self):
        expected = read_json_file(
            os.path.join(CLOUD_ASSEMBLY_DIR, "rootstacknestedstackACD02B51.nested.template.normalized.json"),
            "<current_dir_path>/",
            "",
        )
        self.assertEqual(self.nested_stack.template, expected)

    def test_parent(self):
        self.assertEqual(self.nested_stack.parent, self.stack)


class TestCloudAssemblyTree(TestCase):
    def setUp(self) -> None:
        self.cloud_assembly = CloudAssembly(CLOUD_ASSEMBLY_DIR, SOURCE_DIR)
        self.tree = self.cloud_assembly.tree

    def test_root(self):
        self.assertIsInstance(self.tree.root, CloudAssemblyTreeNode)
        self.assertEqual(self.tree.root.id, "App")

    def test_find_node_by_path(self):
        node = self.tree.find_node_by_path("root-stack/container-function/Resource")
        self.assertIsInstance(node, CloudAssemblyTreeNode)
        self.assertEqual(node.id, "Resource")
        self.assertEqual(node.path, "root-stack/container-function/Resource")


class TestCloudAssemblyTreeNode(TestCase):
    def setUp(self) -> None:
        self.cloud_assembly = CloudAssembly(CLOUD_ASSEMBLY_DIR, SOURCE_DIR)
        self.tree = self.cloud_assembly.tree

    def test_construct_info(self):
        node = self.tree.find_node_by_path("root-stack/container-function/Resource")
        expected = {"fqn": "@aws-cdk/aws-lambda.CfnFunction", "version": "1.95.1"}
        self.assertEqual(node.construct_info, expected)

    def test_fqn(self):
        node = self.tree.find_node_by_path("root-stack/container-function/Resource")
        self.assertEqual(node._fqn, "@aws-cdk/aws-lambda.CfnFunction")

    def test_parent(self):
        node = self.tree.find_node_by_path("root-stack/container-function/Resource")
        parent = self.tree.find_node_by_path("root-stack/container-function")
        self.assertEqual(node.parent, parent)

    def test_children(self):
        node = self.tree.find_node_by_path("root-stack/container-function")
        children = node.childrens
        self.assertIsInstance(children, list)
        self.assertEqual(len(children), 3)
        self.assertIn(self.tree.find_node_by_path("root-stack/container-function/ServiceRole"), children)
        self.assertIn(self.tree.find_node_by_path("root-stack/container-function/AssetImage"), children)
        self.assertIn(self.tree.find_node_by_path("root-stack/container-function/Resource"), children)
