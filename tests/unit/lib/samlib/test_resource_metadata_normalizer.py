import pathlib
from unittest import TestCase

from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer


class TestResourceMetadataNormalizer(TestCase):
    def test_replace_property_with_path(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {
                        "Code": {
                            "S3Bucket": {"Fn::Sub": "cdk-hnb659fds-assets-${AWS::AccountId}-${AWS::Region}"},
                            "S3Key": "00c88ea957f8f667f083d6073f00c49dd2ed7ddd87bb7a3b6f01d014243a3b22.zip",
                        }
                    },
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_replace_all_resources_that_contain_metadata(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {
                        "Code": {
                            "S3Bucket": {"Fn::Sub": "cdk-hnb659fds-assets-${AWS::AccountId}-${AWS::Region}"},
                            "S3Key": "00c88ea957f8f667f083d6073f00c49dd2ed7ddd87bb7a3b6f01d014243a3b22.zip",
                        }
                    },
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                },
                "Resource2": {
                    "Properties": {"SomeRandomProperty": {"Fn::Sub": "${AWS::AccountId}/some_value"}},
                    "Metadata": {"aws:asset:path": "super cool path", "aws:asset:property": "SomeRandomProperty"},
                },
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("super cool path", template_data["Resources"]["Resource2"]["Properties"]["SomeRandomProperty"])

    def test_replace_all_resources_that_contain_image_metadata(self):
        docker_build_args = {"arg1": "val1", "arg2": "val2"}
        asset_path = pathlib.Path("/path", "to", "asset")
        dockerfile_path = pathlib.Path("path", "to", "Dockerfile")
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {
                        "Code": {
                            "ImageUri": {
                                "Fn::Sub": "${AWS::AccountId}.dkr.ecr.${AWS::Region}.${AWS::URLSuffix}/cdk-hnb659fds-container-assets-${AWS::AccountId}-${AWS::Region}:b5d75370ccc2882b90f701c8f98952aae957e85e1928adac8860222960209056"
                            }
                        }
                    },
                    "Metadata": {
                        "aws:asset:path": asset_path,
                        "aws:asset:property": "Code.ImageUri",
                        "aws:asset:dockerfile-path": dockerfile_path,
                        "aws:asset:docker-build-args": docker_build_args,
                    },
                },
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        expected_docker_context_path = str(pathlib.Path("/path", "to", "asset", "path", "to"))
        self.assertEqual("function1", template_data["Resources"]["Function1"]["Properties"]["Code"]["ImageUri"])
        self.assertEqual(
            expected_docker_context_path, template_data["Resources"]["Function1"]["Metadata"]["DockerContext"]
        )
        self.assertEqual("Dockerfile", template_data["Resources"]["Function1"]["Metadata"]["Dockerfile"])
        self.assertEqual(docker_build_args, template_data["Resources"]["Function1"]["Metadata"]["DockerBuildArgs"])

    def test_replace_all_resources_that_contain_image_metadata_windows_paths(self):
        docker_build_args = {"arg1": "val1", "arg2": "val2"}
        asset_path = "C:\\path\\to\\asset"
        dockerfile_path = "rel/path/to/Dockerfile"
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {
                        "Code": {
                            "ImageUri": {
                                "Fn::Sub": "${AWS::AccountId}.dkr.ecr.${AWS::Region}.${AWS::URLSuffix}/cdk-hnb659fds-container-assets-${AWS::AccountId}-${AWS::Region}:b5d75370ccc2882b90f701c8f98952aae957e85e1928adac8860222960209056"
                            }
                        }
                    },
                    "Metadata": {
                        "aws:asset:path": asset_path,
                        "aws:asset:property": "Code.ImageUri",
                        "aws:asset:dockerfile-path": dockerfile_path,
                        "aws:asset:docker-build-args": docker_build_args,
                    },
                },
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        expected_docker_context_path = str(pathlib.Path("C:\\path\\to\\asset").joinpath(pathlib.Path("rel/path/to")))
        self.assertEqual("function1", template_data["Resources"]["Function1"]["Properties"]["Code"]["ImageUri"])
        self.assertEqual(
            expected_docker_context_path, template_data["Resources"]["Function1"]["Metadata"]["DockerContext"]
        )
        self.assertEqual("Dockerfile", template_data["Resources"]["Function1"]["Metadata"]["Dockerfile"])
        self.assertEqual(docker_build_args, template_data["Resources"]["Function1"]["Metadata"]["DockerBuildArgs"])

    def test_tempate_without_metadata(self):
        template_data = {"Resources": {"Function1": {"Properties": {"Code": "some value"}}}}

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_template_without_asset_property(self):
        template_data = {
            "Resources": {
                "Function1": {"Properties": {"Code": "some value"}, "Metadata": {"aws:asset:path": "new path"}}
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_tempalte_without_asset_path(self):
        template_data = {
            "Resources": {
                "Function1": {"Properties": {"Code": "some value"}, "Metadata": {"aws:asset:property": "Code"}}
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_template_with_empty_metadata(self):
        template_data = {"Resources": {"Function1": {"Properties": {"Code": "some value"}, "Metadata": {}}}}

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_replace_of_property_that_does_not_exist(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {},
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_set_skip_build_metadata_for_bundled_assets_metadata_equals_true(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {
                        "aws:asset:path": "new path",
                        "aws:asset:property": "Code",
                        "aws:asset:is-bundled": True,
                    },
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertTrue(template_data["Resources"]["Function1"]["Metadata"]["SkipBuild"])

    def test_no_skip_build_metadata_for_bundled_assets_metadata_equals_false(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {
                        "aws:asset:path": "new path",
                        "aws:asset:property": "Code",
                        "aws:asset:is-bundled": False,
                    },
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertIsNone(template_data["Resources"]["Function1"]["Metadata"].get("SkipBuild"))

    def test_no_cdk_template_parameters_should_not_be_normalized(self):
        template_data = {
            "Parameters": {
                "AssetParameters123456543": {"Type": "String", "Description": 'S3 bucket for asset "12345432"'},
            },
            "Resources": {
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {
                        "aws:asset:path": "new path",
                        "aws:asset:property": "Code",
                        "aws:asset:is-bundled": False,
                    },
                }
            },
        }

        ResourceMetadataNormalizer.normalize(template_data, True)

        self.assertIsNone(template_data["Parameters"]["AssetParameters123456543"].get("Default"))

    def test_cdk_template_parameters_should_be_normalized(self):
        template_data = {
            "Parameters": {
                "AssetParameters123": {"Type": "String", "Description": 'S3 bucket for asset "12345432"'},
                "AssetParameters124": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                    "Default": "/path",
                },
                "AssetParameters125": {
                    "Type": "notString",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParameters126": {"Type": "String", "Description": 'S3 bucket for asset "12345432"'},
                "NotAssetParameters": {"Type": "String", "Description": 'S3 bucket for asset "12345432"'},
            },
            "Resources": {
                "CDKMetadata": {
                    "Type": "AWS::CDK::Metadata",
                    "Properties": {"Analytics": "v2:deflate64:H4s"},
                    "Metadata": {"aws:cdk:path": "Stack/CDKMetadata/Default"},
                },
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {
                        "aws:asset:path": "new path",
                        "aws:asset:property": "Code",
                        "aws:asset:is-bundled": False,
                    },
                },
                "Function2": {
                    "Properties": {"Code": {"Ref": "AssetParameters126"}},
                },
            },
        }

        ResourceMetadataNormalizer.normalize(template_data, True)
        self.assertEquals(template_data["Parameters"]["AssetParameters123"]["Default"], " ")
        self.assertEquals(template_data["Parameters"]["AssetParameters124"]["Default"], "/path")
        self.assertIsNone(template_data["Parameters"]["AssetParameters125"].get("Default"))
        self.assertIsNone(template_data["Parameters"]["AssetParameters126"].get("Default"))
        self.assertIsNone(template_data["Parameters"]["NotAssetParameters"].get("Default"))


class TestResourceMetadataNormalizerGetResourceId(TestCase):
    def test_use_cdk_id_as_resource_id(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {
                "Type": "any:value",
                "Properties": {"key": "value"},
                "Metadata": {"aws:cdk:path": "stack_id/func_cdk_id/Resource"},
            },
            "logical_id",
        )

        self.assertEquals("func_cdk_id", resource_id)

    def test_use_logical_id_as_resource_id_incase_of_invalid_cdk_path(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {"Type": "any:value", "Properties": {"key": "value"}, "Metadata": {"aws:cdk:path": "func_cdk_id"}},
            "logical_id",
        )

        self.assertEquals("logical_id", resource_id)

    def test_use_cdk_id_as_resource_id_for_nested_stack(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {
                "Type": "AWS::CloudFormation::Stack",
                "Properties": {"key": "value"},
                "Metadata": {
                    "aws:cdk:path": "parent_stack_id/nested_stack_id.NestedStack/nested_stack_id.NestedStackResource"
                },
            },
            "logical_id",
        )

        self.assertEquals("nested_stack_id", resource_id)

    def test_use_logical_id_as_resource_id_for_invalid_nested_stack_path(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {
                "Type": "AWS::CloudFormation::Stack",
                "Properties": {"key": "value"},
                "Metadata": {
                    "aws:cdk:path": "parent_stack_id/nested_stack_idNestedStack/nested_stack_id.NestedStackResource"
                },
            },
            "logical_id",
        )

        self.assertEquals("nested_stack_idNestedStack", resource_id)

    def test_use_provided_customer_defined_id(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {
                "Type": "any:value",
                "Properties": {"key": "value"},
                "Metadata": {"SamResourceId": "custom_id", "aws:cdk:path": "stack_id/func_cdk_id/Resource"},
            },
            "logical_id",
        )

        self.assertEquals("custom_id", resource_id)

    def test_use_provided_customer_defined_id_for_nested_stack(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {
                "Type": "AWS::CloudFormation::Stack",
                "Properties": {"key": "value"},
                "Metadata": {
                    "SamResourceId": "custom_nested_stack_id",
                    "aws:cdk:path": "parent_stack_id/nested_stack_id.NestedStack/nested_stack_id.NestedStackResource",
                },
            },
            "logical_id",
        )

        self.assertEquals("custom_nested_stack_id", resource_id)

    def test_use_logical_id_if_metadata_is_not_therer(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {"Type": "any:value", "Properties": {"key": "value"}}, "logical_id"
        )

        self.assertEquals("logical_id", resource_id)

    def test_use_logical_id_if_cdk_path_not_exist(self):
        resource_id = ResourceMetadataNormalizer.get_resource_id(
            {"Type": "any:value", "Properties": {"key": "value"}, "Metadata": {}}, "logical_id"
        )

        self.assertEquals("logical_id", resource_id)
