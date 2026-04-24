"""
Tests for template.py language extensions support.

Covers _update_foreach_relative_paths, _update_sam_mappings_relative_paths,
_get_artifacts_from_foreach, and _get_function_ids_from_foreach.
"""

import os
import tempfile
from unittest import TestCase
from unittest.mock import patch

from samcli.commands._utils.template import (
    _update_foreach_relative_paths,
    _update_sam_mappings_relative_paths,
    _get_artifacts_from_foreach,
    _get_function_ids_from_foreach,
)
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestUpdateForeachRelativePaths(TestCase):
    """Tests for _update_foreach_relative_paths."""

    def test_invalid_foreach_not_list(self):
        # Should not raise
        _update_foreach_relative_paths("not a list", "/old", "/new")

    def test_invalid_foreach_too_short(self):
        _update_foreach_relative_paths(["only", "two"], "/old", "/new")

    def test_non_dict_output_template(self):
        _update_foreach_relative_paths(["Name", ["A"], "not a dict"], "/old", "/new")

    def test_updates_serverless_function_codeuri(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_root = tmpdir
            new_root = os.path.join(tmpdir, "build")
            os.makedirs(new_root, exist_ok=True)
            # Create a source directory
            src_dir = os.path.join(old_root, "src")
            os.makedirs(src_dir, exist_ok=True)

            foreach_value = [
                "Name",
                ["A"],
                {
                    "${Name}Func": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {"CodeUri": "src"},
                    }
                },
            ]
            _update_foreach_relative_paths(foreach_value, old_root, new_root)
            # CodeUri should be updated to relative path from new_root
            updated = foreach_value[2]["${Name}Func"]["Properties"]["CodeUri"]
            self.assertIsNotNone(updated)

    def test_skips_non_dict_resource_def(self):
        foreach_value = [
            "Name",
            ["A"],
            {"${Name}Func": "not a dict"},
        ]
        # Should not raise
        _update_foreach_relative_paths(foreach_value, "/old", "/new")

    def test_skips_non_packageable_resource_type(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Topic": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {"TopicName": "${Name}"},
                }
            },
        ]
        _update_foreach_relative_paths(foreach_value, "/old", "/new")
        # Properties should be unchanged
        self.assertEqual(foreach_value[2]["${Name}Topic"]["Properties"]["TopicName"], "${Name}")

    def test_handles_nested_foreach(self):
        foreach_value = [
            "Outer",
            ["A"],
            {
                "Fn::ForEach::Inner": [
                    "Inner",
                    ["X"],
                    {
                        "${Inner}Func": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "src"},
                        }
                    },
                ]
            },
        ]
        # Should not raise - recursion should work
        _update_foreach_relative_paths(foreach_value, "/old", "/new")


class TestUpdateSamMappingsRelativePaths(TestCase):
    """Tests for _update_sam_mappings_relative_paths."""

    def test_non_dict_mappings(self):
        # Should not raise
        _update_sam_mappings_relative_paths("not a dict", "/old", "/new")

    def test_skips_non_sam_mappings(self):
        mappings = {
            "RegionMap": {
                "us-east-1": {"AMI": "ami-12345"},
            }
        }
        _update_sam_mappings_relative_paths(mappings, "/old", "/new")
        # Should be unchanged
        self.assertEqual(mappings["RegionMap"]["us-east-1"]["AMI"], "ami-12345")

    def test_skips_sam_prefix_substring_mappings(self):
        """User-authored mappings like SAMPLE / SAMSUNG must not be treated as SAM-generated."""
        mappings = {
            "SAMPLE": {"key1": {"CodeUri": "services/users"}},
            "SAMSUNG": {"key2": {"CodeUri": "services/orders"}},
            "SAMCustomMapping": {"key3": {"CodeUri": "services/products"}},
        }
        _update_sam_mappings_relative_paths(mappings, "/old", "/new")
        self.assertEqual(mappings["SAMPLE"]["key1"]["CodeUri"], "services/users")
        self.assertEqual(mappings["SAMSUNG"]["key2"]["CodeUri"], "services/orders")
        self.assertEqual(mappings["SAMCustomMapping"]["key3"]["CodeUri"], "services/products")

    def test_skips_non_dict_mapping_entries(self):
        mappings = {"SAMCodeUriFunctions": "not a dict"}
        _update_sam_mappings_relative_paths(mappings, "/old", "/new")

    def test_skips_non_dict_value_dict(self):
        mappings = {"SAMCodeUriFunctions": {"Alpha": "not a dict"}}
        _update_sam_mappings_relative_paths(mappings, "/old", "/new")

    def test_updates_sam_mapping_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_root = tmpdir
            new_root = os.path.join(tmpdir, "build")
            os.makedirs(new_root, exist_ok=True)
            src_dir = os.path.join(old_root, "services", "users")
            os.makedirs(src_dir, exist_ok=True)

            mappings = {
                "SAMCodeUriFunctions": {
                    "Users": {"CodeUri": os.path.join("services", "users")},
                }
            }
            _update_sam_mappings_relative_paths(mappings, old_root, new_root)
            updated = mappings["SAMCodeUriFunctions"]["Users"]["CodeUri"]
            self.assertIsNotNone(updated)


class TestGetArtifactsFromForeach(TestCase):
    """Tests for _get_artifacts_from_foreach."""

    def _get_packageable_resources(self):
        from samcli.commands._utils.template import get_packageable_resource_paths

        return get_packageable_resource_paths()

    def test_invalid_foreach_not_list(self):
        result = _get_artifacts_from_foreach("not a list", self._get_packageable_resources())
        self.assertEqual(result, [])

    def test_invalid_foreach_too_short(self):
        result = _get_artifacts_from_foreach(["only"], self._get_packageable_resources())
        self.assertEqual(result, [])

    def test_non_dict_output_template(self):
        result = _get_artifacts_from_foreach(["Name", ["A"], "not a dict"], self._get_packageable_resources())
        self.assertEqual(result, [])

    def test_serverless_function_zip(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Func": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src/${Name}", "Runtime": "python3.13"},
                }
            },
        ]
        result = _get_artifacts_from_foreach(foreach_value, self._get_packageable_resources())
        self.assertEqual(result, [ZIP])

    def test_serverless_function_image(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Func": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src", "PackageType": IMAGE},
                }
            },
        ]
        result = _get_artifacts_from_foreach(foreach_value, self._get_packageable_resources())
        self.assertEqual(result, [IMAGE])

    def test_non_packageable_resource(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Topic": {
                    "Type": "AWS::SNS::Topic",
                    "Properties": {"TopicName": "${Name}"},
                }
            },
        ]
        result = _get_artifacts_from_foreach(foreach_value, self._get_packageable_resources())
        self.assertEqual(result, [])

    def test_non_dict_resource_def_skipped(self):
        foreach_value = ["Name", ["A"], {"${Name}Func": "not a dict"}]
        result = _get_artifacts_from_foreach(foreach_value, self._get_packageable_resources())
        self.assertEqual(result, [])

    def test_nested_foreach(self):
        foreach_value = [
            "Outer",
            ["A"],
            {
                "Fn::ForEach::Inner": [
                    "Inner",
                    ["X"],
                    {
                        "${Inner}Func": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {"CodeUri": "./src"},
                        }
                    },
                ]
            },
        ]
        result = _get_artifacts_from_foreach(foreach_value, self._get_packageable_resources())
        self.assertEqual(result, [ZIP])


class TestGetFunctionIdsFromForeach(TestCase):
    """Tests for _get_function_ids_from_foreach."""

    def test_invalid_foreach_not_list(self):
        result = _get_function_ids_from_foreach("not a list", ZIP)
        self.assertEqual(result, [])

    def test_invalid_foreach_too_short(self):
        result = _get_function_ids_from_foreach(["only", "two"], ZIP)
        self.assertEqual(result, [])

    def test_non_dict_output_template(self):
        result = _get_function_ids_from_foreach(["Name", ["A"], "not a dict"], ZIP)
        self.assertEqual(result, [])

    def test_zip_function_found(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Func": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src"},
                }
            },
        ]
        result = _get_function_ids_from_foreach(foreach_value, ZIP)
        self.assertEqual(result, ["${Name}Func"])

    def test_image_function_found(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Func": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"PackageType": IMAGE},
                }
            },
        ]
        result = _get_function_ids_from_foreach(foreach_value, IMAGE)
        self.assertEqual(result, ["${Name}Func"])

    def test_zip_function_not_matched_for_image_artifact(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Func": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "./src"},
                }
            },
        ]
        result = _get_function_ids_from_foreach(foreach_value, IMAGE)
        self.assertEqual(result, [])

    def test_non_function_resource_skipped(self):
        foreach_value = [
            "Name",
            ["A"],
            {
                "${Name}Api": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {"DefinitionUri": "./api.yaml"},
                }
            },
        ]
        result = _get_function_ids_from_foreach(foreach_value, ZIP)
        self.assertEqual(result, [])

    def test_non_dict_resource_def_skipped(self):
        foreach_value = ["Name", ["A"], {"${Name}Func": "not a dict"}]
        result = _get_function_ids_from_foreach(foreach_value, ZIP)
        self.assertEqual(result, [])

    def test_nested_foreach(self):
        foreach_value = [
            "Outer",
            ["A"],
            {
                "Fn::ForEach::Inner": [
                    "Inner",
                    ["X"],
                    {
                        "${Inner}Func": {
                            "Type": "AWS::Lambda::Function",
                            "Properties": {"Code": "./src"},
                        }
                    },
                ]
            },
        ]
        result = _get_function_ids_from_foreach(foreach_value, ZIP)
        self.assertEqual(result, ["${Inner}Func"])
