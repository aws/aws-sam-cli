"""Test Terraform prepare enrichment"""
from unittest.mock import Mock, call, patch
from parameterized import parameterized
from subprocess import CalledProcessError

from tests.unit.hook_packages.terraform.hooks.prepare.prepare_base import PrepareHookUnitBase
from samcli.hook_packages.terraform.hooks.prepare.types import (
    SamMetadataResource,
)
from samcli.hook_packages.terraform.hooks.prepare.enrich import (
    enrich_resources_and_generate_makefile,
    _enrich_zip_lambda_function,
    _enrich_image_lambda_function,
    _enrich_lambda_layer,
    _validate_referenced_resource_layer_matches_metadata_type,
    _get_source_code_path,
    _get_relevant_cfn_resource,
    _validate_referenced_resource_matches_sam_metadata_type,
    _get_python_command_name,
)
from samcli.hook_packages.terraform.hooks.prepare.types import TFResource
from samcli.lib.hook.exceptions import PrepareHookException
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
)
from samcli.hook_packages.terraform.hooks.prepare.exceptions import InvalidSamMetadataPropertiesException
from samcli.hook_packages.terraform.hooks.prepare.translate import NULL_RESOURCE_PROVIDER_NAME


class TestPrepareHookMakefile(PrepareHookUnitBase):
    def setUp(self):
        super().setUp()

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_resources_and_generate_makefile_zip_functions(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }
        zip_function_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file2.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func2", "SkipBuild": True},
        }
        cfn_resources = {
            "logical_id1": zip_function_1,
            "logical_id2": zip_function_2,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            [(zip_function_1, "logical_id1")],
            [(zip_function_2, "logical_id2")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_2_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        expected_zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }
        expected_zip_function_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "src/code/path2",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func2",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        expected_cfn_resources = {
            "logical_id1": expected_zip_function_1,
            "logical_id2": expected_zip_function_2,
        }

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        self.assertEqual(cfn_resources, expected_cfn_resources)

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(expected_cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_layer_matches_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_resources_and_generate_makefile_layers(
        self,
        mock_get_lambda_layer_source_code_path,
        mock_validate_referenced_resource_layer_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"
        mock_get_lambda_layer_source_code_path.side_effect = ["src/code/path1"]
        lambda_layer = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_layer_version.{self.lambda_layer_name}", "SkipBuild": True},
        }
        cfn_resources = {
            "logical_id1": lambda_layer,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            [(lambda_layer, "logical_id1")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_layer_resource_zip_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        expected_layer = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": f"aws_lambda_layer_version.{self.lambda_layer_name}",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        expected_cfn_resources = {
            "logical_id1": expected_layer,
        }

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        self.assertEqual(cfn_resources, expected_cfn_resources)

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(expected_cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._enrich_image_lambda_function")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._enrich_zip_lambda_function")
    def test_enrich_resources_and_generate_makefile_mock_enrich_zip_functions(
        self,
        mock_enrich_zip_lambda_function,
        mock_enrich_image_lambda_function,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }
        zip_function_2 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file2.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func2", "SkipBuild": True},
        }
        cfn_resources = {
            "logical_id1": zip_function_1,
            "logical_id2": zip_function_2,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            [(zip_function_1, "logical_id1")],
            [(zip_function_2, "logical_id2")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_lambda_function_resource_zip_2_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        mock_enrich_zip_lambda_function.assert_has_calls(
            [
                call(
                    self.tf_lambda_function_resource_zip_sam_metadata,
                    zip_function_1,
                    "logical_id1",
                    "/terraform/project/root",
                    "/output/dir",
                ),
                call(
                    self.tf_lambda_function_resource_zip_2_sam_metadata,
                    zip_function_2,
                    "logical_id2",
                    "/terraform/project/root",
                    "/output/dir",
                ),
            ]
        )
        mock_enrich_image_lambda_function.assert_not_called()

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_mapped_resource_zip_function(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }
        mock_get_relevant_cfn_resource.side_effect = [
            (zip_function_1, "logical_id1"),
        ]

        expected_zip_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_function_common_properties,
                "Code": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        _enrich_zip_lambda_function(
            self.tf_lambda_function_resource_zip_sam_metadata,
            zip_function_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        self.assertEqual(zip_function_1, expected_zip_function_1)

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_mapped_resource_zip_layer(
        self,
        mock_get_lambda_layer_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_layer_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        lambda_layer_1 = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "file.zip",
            },
            "Metadata": {"SamResourceId": f"aws_lambda_layer_version.lambda_layer", "SkipBuild": True},
        }
        mock_get_relevant_cfn_resource.side_effect = [
            (lambda_layer_1, "logical_id1"),
        ]

        expected_lambda_layer_1 = {
            "Type": AWS_LAMBDA_LAYERVERSION,
            "Properties": {
                **self.expected_cfn_layer_common_properties,
                "Content": "src/code/path1",
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_layer_version.lambda_layer",
                "SkipBuild": False,
                "BuildMethod": "makefile",
                "ContextPath": "/output/dir",
                "WorkingDirectory": "/terraform/project/root",
                "ProjectRootDirectory": "/terraform/project/root",
            },
        }

        _enrich_lambda_layer(
            self.tf_lambda_layer_resource_zip_sam_metadata,
            lambda_layer_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        self.assertEqual(lambda_layer_1, expected_lambda_layer_1)

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_resources_and_generate_makefile_image_functions(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
                "Code": {
                    "ImageUri": "image/uri:tag",
                },
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }

        cfn_resources = {
            "logical_id1": image_function_1,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            [(image_function_1, "logical_id1")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_image_package_type_lambda_function_resource_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        expected_image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "DockerContext": "src/code/path1",
                "Dockerfile": "Dockerfile",
                "DockerTag": "2.0",
                "DockerBuildArgs": {"FOO": "bar"},
            },
        }

        expected_cfn_resources = {
            "logical_id1": expected_image_function_1,
        }

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        self.assertEqual(cfn_resources, expected_cfn_resources)

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_mapped_resource_image_function(
        self,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
                "Code": {
                    "ImageUri": "image/uri:tag",
                },
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }

        mock_get_relevant_cfn_resource.side_effect = [
            (image_function_1, "logical_id1"),
        ]

        expected_image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
            },
            "Metadata": {
                "SamResourceId": "aws_lambda_function.func1",
                "SkipBuild": False,
                "DockerContext": "src/code/path1",
                "Dockerfile": "Dockerfile",
                "DockerTag": "2.0",
                "DockerBuildArgs": {"FOO": "bar"},
            },
        }

        _enrich_image_lambda_function(
            self.tf_image_package_type_lambda_function_resource_sam_metadata,
            image_function_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        self.assertEqual(image_function_1, expected_image_function_1)

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_python_command_name")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.generate_makefile_rule_for_lambda_resource")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._enrich_image_lambda_function")
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._enrich_zip_lambda_function")
    def test_enrich_resources_and_generate_makefile_mock_enrich_image_functions(
        self,
        mock_enrich_zip_lambda_function,
        mock_enrich_image_lambda_function,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
        mock_generate_makefile_rule_for_lambda_resource,
        mock_generate_makefile,
        mock_get_python_command_name,
    ):
        mock_get_python_command_name.return_value = "python"

        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
                "Code": {
                    "ImageUri": "image/uri:tag",
                },
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }

        cfn_resources = {
            "logical_id1": image_function_1,
        }
        mock_get_relevant_cfn_resource.side_effect = [
            [(image_function_1, "logical_id1")],
        ]
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource=self.tf_image_package_type_lambda_function_resource_sam_metadata,
                config_resource=TFResource("", "", None, {}),
            ),
        ]

        makefile_rules = [Mock() for _ in sam_metadata_resources]
        mock_generate_makefile_rule_for_lambda_resource.side_effect = makefile_rules

        enrich_resources_and_generate_makefile(
            sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
        )
        mock_enrich_image_lambda_function.assert_called_once_with(
            self.tf_image_package_type_lambda_function_resource_sam_metadata,
            image_function_1,
            "logical_id1",
            "/terraform/project/root",
            "/output/dir",
        )
        mock_enrich_zip_lambda_function.assert_not_called()

        mock_generate_makefile_rule_for_lambda_resource.assert_has_calls(
            [
                call(
                    sam_metadata_resources[i],
                    list(cfn_resources.keys())[i],
                    "/terraform/project/root",
                    "python",
                    "/output/dir",
                )
                for i in range(len(sam_metadata_resources))
            ]
        )

        mock_generate_makefile.assert_called_once_with(makefile_rules, "/output/dir")

    @parameterized.expand(
        [
            ("ABCDEFG",),
            ('"ABCDEFG"',),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_relevant_cfn_resource")
    @patch(
        "samcli.hook_packages.terraform.hooks.prepare.enrich._validate_referenced_resource_matches_sam_metadata_type"
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_source_code_path")
    def test_enrich_mapped_resource_image_function_invalid_docker_args(
        self,
        docker_args_value,
        mock_get_lambda_function_source_code_path,
        mock_validate_referenced_resource_matches_sam_metadata_type,
        mock_get_relevant_cfn_resource,
    ):
        mock_get_lambda_function_source_code_path.side_effect = ["src/code/path1", "src/code/path2"]
        image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
                "Code": {
                    "ImageUri": "image/uri:tag",
                },
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }

        mock_get_relevant_cfn_resource.side_effect = [
            (image_function_1, "logical_id1"),
        ]
        sam_metadata_resource = {
            **self.tf_sam_metadata_resource_common_attributes,
            "values": {
                "triggers": {
                    "resource_name": f"aws_lambda_function.{self.image_function_name}",
                    "docker_build_args": docker_args_value,
                    "docker_context": "context",
                    "docker_file": "Dockerfile",
                    "docker_tag": "2.0",
                    "resource_type": "IMAGE_LAMBDA_FUNCTION",
                },
            },
            "address": f"null_resource.sam_metadata_{self.image_function_name}",
            "name": f"sam_metadata_{self.image_function_name}",
        }

        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg="The sam metadata resource null_resource.sam_metadata_func1 should contain a valid json encoded "
            "string for the lambda function docker build arguments.",
        ):
            _enrich_image_lambda_function(
                sam_metadata_resource, image_function_1, "logical_id1", "/terraform/project/root", "/output/dir"
            )

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._get_python_command_name")
    def test_enrich_resources_and_generate_makefile_invalid_source_type(
        self,
        mock_get_python_command_name,
    ):
        image_function_1 = {
            "Type": CFN_AWS_LAMBDA_FUNCTION,
            "Properties": {
                **self.expected_cfn_image_package_type_function_common_properties,
                "ImageConfig": {
                    "Command": ["cmd1", "cmd2"],
                    "EntryPoint": ["entry1", "entry2"],
                    "WorkingDirectory": "/working/dir/path",
                },
                "Code": {
                    "ImageUri": "image/uri:tag",
                },
            },
            "Metadata": {"SamResourceId": f"aws_lambda_function.func1", "SkipBuild": True},
        }

        cfn_resources = {
            "logical_id1": image_function_1,
        }
        sam_metadata_resources = [
            SamMetadataResource(
                current_module_address=None,
                resource={
                    **self.tf_sam_metadata_resource_common_attributes,
                    "values": {
                        "triggers": {
                            "resource_name": f"aws_lambda_function.{self.image_function_name}",
                            "docker_build_args": '{"FOO":"bar"}',
                            "docker_context": "context",
                            "docker_file": "Dockerfile",
                            "docker_tag": "2.0",
                            "resource_type": "Invalid_resource_type",
                        },
                    },
                    "address": f"null_resource.sam_metadata_func1",
                    "name": f"sam_metadata_func1",
                },
                config_resource=TFResource("", "", None, {}),
            ),
        ]
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg="The resource type Invalid_resource_type found in the sam metadata resource "
            "null_resource.sam_metadata_func1 is not a correct resource type. The resource type should be one of "
            "these values [ZIP_LAMBDA_FUNCTION, IMAGE_LAMBDA_FUNCTION]",
        ):
            enrich_resources_and_generate_makefile(
                sam_metadata_resources, cfn_resources, "/output/dir", "/terraform/project/root", {}
            )

    def test_validate_referenced_layer_resource_matches_sam_metadata_type_valid_types(self):
        cfn_resource = self.expected_cfn_layer_resource_zip
        sam_metadata_attributes = self.tf_lambda_layer_resource_zip_sam_metadata.get("values").get("triggers")
        try:
            _validate_referenced_resource_layer_matches_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address"
            )
        except InvalidSamMetadataPropertiesException:
            self.fail("The testing sam metadata resource type should be valid.")

    @parameterized.expand(
        [
            (
                "expected_cfn_lambda_function_resource_zip",
                "tf_lambda_layer_resource_zip_sam_metadata",
            ),
            (
                "expected_cfn_image_package_type_lambda_function_resource",
                "tf_lambda_layer_resource_zip_sam_metadata",
            ),
        ]
    )
    def test_validate_referenced_resource_layer_matches_sam_metadata_type_invalid_types(
        self, cfn_resource_name, sam_metadata_attributes_name
    ):
        cfn_resource = self.__getattribute__(cfn_resource_name)
        sam_metadata_attributes = self.__getattribute__(sam_metadata_attributes_name).get("values").get("triggers")
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg=f"The sam metadata resource resource_address is referring to a resource that does not "
            f"match the resource type AWS::Lambda::LayerVersion.",
        ):
            _validate_referenced_resource_layer_matches_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address"
            )

    @parameterized.expand(
        [
            ("/src/code/path", None, "/src/code/path", True),
            ("src/code/path", None, "src/code/path", False),
            ('"/src/code/path"', None, "/src/code/path", True),
            ('"src/code/path"', None, "src/code/path", False),
            ('{"path":"/src/code/path"}', "path", "/src/code/path", True),
            ('{"path":"src/code/path"}', "path", "src/code/path", False),
            ({"path": "/src/code/path"}, "path", "/src/code/path", True),
            ({"path": "src/code/path"}, "path", "src/code/path", False),
            ('["/src/code/path"]', "None", "/src/code/path", True),
            ('["src/code/path"]', "None", "src/code/path", False),
            (["/src/code/path"], "None", "/src/code/path", True),
            (["src/code/path"], "None", "src/code/path", False),
            ('["/src/code/path", "/src/code/path2"]', "None", "/src/code/path", True),
            ('["src/code/path", "src/code/path2"]', "None", "src/code/path", False),
            (["/src/code/path", "/src/code/path2"], "None", "/src/code/path", True),
            (["src/code/path", "/src/code/path2"], "None", "src/code/path", False),
            ('[{"path":"/src/code/path"}]', "path", "/src/code/path", True),
            ('[{"path":"src/code/path"}]', "path", "src/code/path", False),
            ([{"path": "/src/code/path"}], "path", "/src/code/path", True),
            ([{"path": "src/code/path"}], "path", "src/code/path", False),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.os")
    def test_get_lambda_function_source_code_path_valid_metadata_resource(
        self, original_source_code, source_code_property, expected_path, is_abs, mock_os
    ):
        mock_path = Mock()
        mock_os.path = mock_path
        mock_isabs = Mock()
        mock_isabs.return_value = is_abs
        mock_path.isabs = mock_isabs

        mock_exists = Mock()
        mock_exists.return_value = True
        mock_path.exists = mock_exists

        if not is_abs:
            mock_normpath = Mock()
            mock_normpath.return_value = f"/project/root/dir/{expected_path}"
            expected_path = f"/project/root/dir/{expected_path}"
            mock_path.normpath = mock_normpath
            mock_join = Mock()
            mock_join.return_value = expected_path
            mock_path.join = mock_join
        sam_metadata_attributes = {
            **self.tf_zip_function_sam_metadata_properties,
            "original_source_code": original_source_code,
        }
        if source_code_property:
            sam_metadata_attributes = {
                **sam_metadata_attributes,
                "source_code_property": source_code_property,
            }
        sam_resource = {"values": {"triggers": sam_metadata_attributes}}
        path = _get_source_code_path(
            sam_resource,
            "resource_address",
            "/project/root/dir",
            "original_source_code",
            "source_code_property",
            "source code",
        )
        self.assertEqual(path, expected_path)

    @parameterized.expand(
        [
            (
                "/src/code/path",
                None,
                False,
                "The sam metadata resource resource_address should contain a valid lambda function source code path",
            ),
            (
                None,
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function source code in "
                "property original_source_code",
            ),
            (
                '{"path":"/src/code/path"}',
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function source code property in "
                "property source_code_property as the original_source_code value is an object",
            ),
            (
                {"path": "/src/code/path"},
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function source code property "
                "in property source_code_property as the original_source_code value is an object",
            ),
            (
                '{"path":"/src/code/path"}',
                "path1",
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code "
                "property in property source_code_property as the original_source_code value is an object",
            ),
            (
                {"path": "/src/code/path"},
                "path1",
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code "
                "property in property source_code_property as the original_source_code value is an object",
            ),
            (
                "[]",
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function  source code in "
                "property original_source_code, and it should not be an empty list",
            ),
            (
                [],
                None,
                True,
                "The sam metadata resource resource_address should contain the lambda function  source code in "
                "property original_source_code, and it should not be an empty list",
            ),
            (
                "[null]",
                None,
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code in "
                "property original_source_code",
            ),
            (
                [None],
                None,
                True,
                "The sam metadata resource resource_address should contain a valid lambda function source code in "
                "property original_source_code",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.os")
    def test_get_lambda_function_source_code_path_invalid_metadata_resources(
        self, original_source_code, source_code_property, does_exist, exception_message, mock_os
    ):
        mock_path = Mock()
        mock_os.path = mock_path
        mock_isabs = Mock()
        mock_isabs.return_value = True
        mock_path.isabs = mock_isabs

        mock_exists = Mock()
        mock_exists.return_value = does_exist
        mock_path.exists = mock_exists

        sam_metadata_attributes = {
            **self.tf_zip_function_sam_metadata_properties,
            "original_source_code": original_source_code,
        }
        if source_code_property:
            sam_metadata_attributes = {
                **sam_metadata_attributes,
                "source_code_property": source_code_property,
            }
        with self.assertRaises(InvalidSamMetadataPropertiesException, msg=exception_message):
            _get_source_code_path(
                sam_metadata_attributes,
                "resource_address",
                "/project/root/dir",
                "original_source_code",
                "source_code_property",
                "source code",
            )

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.build_cfn_logical_id")
    def test_get_relevant_cfn_resource(self, mock_build_cfn_logical_id):
        sam_metadata_resource = SamMetadataResource(
            current_module_address="module.mymodule1",
            resource={
                **self.tf_lambda_function_resource_zip_2_sam_metadata,
                "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
            },
            config_resource=TFResource("", "", None, {}),
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_build_cfn_logical_id.side_effect = ["ABCDEFG"]
        resources_list = _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources, {})
        self.assertEqual(len(resources_list), 1)
        relevant_resource, return_logical_id = resources_list[0]

        mock_build_cfn_logical_id.assert_called_once_with(
            f"module.mymodule1.aws_lambda_function.{self.zip_function_name_2}"
        )
        self.assertEqual(relevant_resource, self.expected_cfn_lambda_function_resource_zip_2)
        self.assertEqual(return_logical_id, "ABCDEFG")

    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich._calculate_configuration_attribute_value_hash")
    def test_get_relevant_cfn_resource_for_metadata_does_not_contain_resource_name(
        self, mock_calculate_configuration_attribute_value_hash
    ):
        sam_metadata_resource = SamMetadataResource(
            current_module_address="module.mymodule1",
            resource={
                "type": "null_resource",
                "provider_name": NULL_RESOURCE_PROVIDER_NAME,
                "values": {
                    "triggers": {
                        "built_output_path": "builds/func2.zip",
                        "original_source_code": "./src/lambda_func2",
                        "resource_type": "ZIP_LAMBDA_FUNCTION",
                    }
                },
                "name": f"sam_metadata_{self.zip_function_name_2}",
                "address": f"module.mymodule1.null_resource.sam_metadata_{self.zip_function_name_2}",
            },
            config_resource=TFResource("", "", None, {}),
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_calculate_configuration_attribute_value_hash.side_effect = ["code_hash"]
        lambda_resources_code_map = {"zip_code_hash": [(self.expected_cfn_lambda_function_resource_zip_2, "ABCDEFG")]}
        resources_list = _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources, lambda_resources_code_map)
        self.assertEqual(len(resources_list), 1)
        relevant_resource, return_logical_id = resources_list[0]

        self.assertEqual(relevant_resource, self.expected_cfn_lambda_function_resource_zip_2)
        self.assertEqual(return_logical_id, "ABCDEFG")
        mock_calculate_configuration_attribute_value_hash.assert_has_calls([call("builds/func2.zip")])

    @parameterized.expand(
        [
            (
                None,
                "module.mymodule1",
                ["ABCDEFG"],
                "AWS SAM CLI expects the sam metadata resource null_resource.sam_metadata_func2 to contain a resource name "
                "that will be enriched using this metadata resource",
            ),
            (
                "resource_name_value",
                None,
                ["Not_valid"],
                "There is no resource found that match the provided resource name null_resource.sam_metadata_func2",
            ),
            (
                "resource_name_value",
                "module.mymodule1",
                ["Not_valid", "Not_valid"],
                "There is no resource found that match the provided resource name null_resource.sam_metadata_func2",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.build_cfn_logical_id")
    def test_get_relevant_cfn_resource_exceptions(
        self, resource_name, module_name, build_logical_id_output, exception_message, mock_build_cfn_logical_id
    ):
        sam_metadata_resource = SamMetadataResource(
            current_module_address=module_name,
            resource={
                **self.tf_sam_metadata_resource_common_attributes,
                "values": {
                    "triggers": {
                        "built_output_path": "builds/func2.zip",
                        "original_source_code": "./src/lambda_func2",
                        "resource_name": resource_name,
                        "resource_type": "ZIP_LAMBDA_FUNCTION",
                    },
                },
                "address": "null_resource.sam_metadata_func2",
                "name": "sam_metadata_func2",
            },
            config_resource=TFResource("", "", None, {}),
        )
        cfn_resources = {
            "ABCDEFG": self.expected_cfn_lambda_function_resource_zip_2,
            "logical_id_3": self.expected_cfn_lambda_function_resource_zip_3,
        }
        mock_build_cfn_logical_id.side_effect = build_logical_id_output
        with self.assertRaises(InvalidSamMetadataPropertiesException, msg=exception_message):
            _get_relevant_cfn_resource(sam_metadata_resource, cfn_resources, {})

    @parameterized.expand(
        [
            ("expected_cfn_lambda_function_resource_zip", "tf_lambda_function_resource_zip_sam_metadata", "Zip"),
            (
                "expected_cfn_image_package_type_lambda_function_resource",
                "tf_image_package_type_lambda_function_resource_sam_metadata",
                "Image",
            ),
        ]
    )
    def test_validate_referenced_resource_matches_sam_metadata_type_valid_types(
        self, cfn_resource_name, sam_metadata_attributes_name, expected_package_type
    ):
        cfn_resource = self.__getattribute__(cfn_resource_name)
        sam_metadata_attributes = self.__getattribute__(sam_metadata_attributes_name).get("values").get("triggers")
        try:
            _validate_referenced_resource_matches_sam_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address", expected_package_type
            )
        except InvalidSamMetadataPropertiesException:
            self.fail("The testing sam metadata resource type should be valid.")

    @parameterized.expand(
        [
            (
                "expected_cfn_lambda_function_resource_zip",
                "tf_image_package_type_lambda_function_resource_sam_metadata",
                "Image",
                "IMAGE_LAMBDA_FUNCTION",
            ),
            (
                "expected_cfn_image_package_type_lambda_function_resource",
                "tf_lambda_function_resource_zip_sam_metadata",
                "Zip",
                "ZIP_LAMBDA_FUNCTION",
            ),
        ]
    )
    def test_validate_referenced_resource_matches_sam_metadata_type_invalid_types(
        self, cfn_resource_name, sam_metadata_attributes_name, expected_package_type, metadata_source_type
    ):
        cfn_resource = self.__getattribute__(cfn_resource_name)
        sam_metadata_attributes = self.__getattribute__(sam_metadata_attributes_name).get("values").get("triggers")
        with self.assertRaises(
            InvalidSamMetadataPropertiesException,
            msg=f"The sam metadata resource resource_address is referring to a resource that does not "
            f"match the resource type {metadata_source_type}.",
        ):
            _validate_referenced_resource_matches_sam_metadata_type(
                cfn_resource, sam_metadata_attributes, "resource_address", expected_package_type
            )

    @parameterized.expand(
        [
            ([CalledProcessError(-2, "python3 --version"), Mock(stdout="Python 3.8.10")], "py3"),
            ([Mock(stdout="Python 3.7.12"), CalledProcessError(-2, "py3 --version")], "python3"),
            ([Mock(stdout="Python 3.7")], "python3"),
            ([Mock(stdout="Python 3.7.0")], "python3"),
            ([Mock(stdout="Python 3.7.12")], "python3"),
            ([Mock(stdout="Python 3.8")], "python3"),
            ([Mock(stdout="Python 3.8.0")], "python3"),
            ([Mock(stdout="Python 3.8.12")], "python3"),
            ([Mock(stdout="Python 3.9")], "python3"),
            ([Mock(stdout="Python 3.9.0")], "python3"),
            ([Mock(stdout="Python 3.9.12")], "python3"),
            ([Mock(stdout="Python 3.10")], "python3"),
            ([Mock(stdout="Python 3.10.0")], "python3"),
            ([Mock(stdout="Python 3.10.12")], "python3"),
            (
                [
                    Mock(stdout="Python 3.6.10"),
                    Mock(stdout="Python 3.0.10"),
                    Mock(stdout="Python 2.7.10"),
                    Mock(stdout="Python 3.7.12"),
                ],
                "py",
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.run")
    def test_get_python_command_name(self, mock_run_side_effect, expected_python_command, mock_subprocess_run):
        mock_subprocess_run.side_effect = mock_run_side_effect

        python_command = _get_python_command_name()
        self.assertEqual(python_command, expected_python_command)

    @parameterized.expand(
        [
            (
                [
                    CalledProcessError(-2, "python3 --version"),
                    CalledProcessError(-2, "py3 --version"),
                    CalledProcessError(-2, "python --version"),
                    CalledProcessError(-2, "py --version"),
                ],
            ),
            (
                [
                    Mock(stdout="Python 3"),
                    Mock(stdout="Python 3.0"),
                    Mock(stdout="Python 3.0.10"),
                    Mock(stdout="Python 3.6"),
                ],
            ),
            (
                [
                    Mock(stdout="Python 3.6.10"),
                    Mock(stdout="Python 2"),
                    Mock(stdout="Python 2.7"),
                    Mock(stdout="Python 2.7.10"),
                ],
            ),
            (
                [
                    Mock(stdout="Python 4"),
                    Mock(stdout="Python 4.7"),
                    Mock(stdout="Python 4.7.10"),
                    Mock(stdout="Python 4.7.10"),
                ],
            ),
        ]
    )
    @patch("samcli.hook_packages.terraform.hooks.prepare.enrich.run")
    def test_get_python_command_name_python_not_found(self, mock_run_side_effect, mock_subprocess_run):
        mock_subprocess_run.side_effect = mock_run_side_effect

        expected_error_msg = "Python not found. Please ensure that python 3.7 or above is installed."
        with self.assertRaises(PrepareHookException, msg=expected_error_msg):
            _get_python_command_name()
