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
        self.assertEqual(True, template_data["Resources"]["Function1"]["Metadata"]["SamNormalized"])
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

    def test_cdk_resource_id_is_used(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {
                        "Code": {
                            "S3Bucket": {"Fn::Sub": "cdk-hnb659fds-assets-${AWS::AccountId}-${AWS::Region}"},
                            "S3Key": "00c88ea957f8f667f083d6073f00c49dd2ed7ddd87bb7a3b6f01d014243a3b22.zip",
                        }
                    },
                    "Metadata": {
                        "aws:cdk:path": "Stack/CDKFunction1/Resource",
                        "aws:asset:path": "new path",
                        "aws:asset:property": "Code",
                    },
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual(True, template_data["Resources"]["Function1"]["Metadata"]["SamNormalized"])
        self.assertEqual("CDKFunction1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

    def test_tempate_without_metadata(self):
        template_data = {"Resources": {"Function1": {"Properties": {"Code": "some value"}}}}

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

    def test_template_without_asset_property(self):
        template_data = {
            "Resources": {
                "Function1": {"Properties": {"Code": "some value"}, "Metadata": {"aws:asset:path": "new path"}}
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

    def test_template_without_asset_path(self):
        template_data = {
            "Resources": {
                "Function1": {"Properties": {"Code": "some value"}, "Metadata": {"aws:asset:property": "Code"}}
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

    def test_template_with_empty_metadata(self):
        template_data = {"Resources": {"Function1": {"Properties": {"Code": "some value"}, "Metadata": {}}}}

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

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
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])

    def test_cdk_template_parameters_should_be_normalized(self):
        template_data = {
            "Parameters": {
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652998": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParametersb9866fd422d32492C62394e8c406ab4004f0c80364BAB4957e67e31cf1130481ArtifactHash0A65c998": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3Bucket0A652998": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3VersionKey0A652998": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652999": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                    "Default": "/path",
                },
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652900": {
                    "Type": "notString",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652345": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652345123": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
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
                    "Properties": {
                        "Code": {
                            "Ref": "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652345"
                        }
                    },
                },
                "NestedStack": {
                    "Type": "AWS::CloudFormation::Stack",
                    "Properties": {
                        "TemplateURL": "Some Value",
                        "Parameters": {
                            "referencetoCDKV1SupportDemoStackAssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652998": {
                                "Ref": "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652998"
                            }
                        },
                    },
                    "Metadata": {
                        "aws:cdk:path": "Stack/Level1Stack.NestedStack/Level1Stack.NestedStackResource",
                        "aws:asset:path": "Level1HStackBC5D5417.nested.template.json",
                        "aws:asset:property": "TemplateURL",
                    },
                },
            },
        }

        ResourceMetadataNormalizer.normalize(template_data, True)
        self.assertEqual(
            template_data["Resources"]["NestedStack"]["Properties"]["TemplateURL"],
            "Level1HStackBC5D5417.nested.template.json",
        )
        self.assertEqual(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652998"
            ]["Default"],
            " ",
        )
        self.assertEqual(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492C62394e8c406ab4004f0c80364BAB4957e67e31cf1130481ArtifactHash0A65c998"
            ]["Default"],
            " ",
        )
        self.assertEqual(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3Bucket0A652998"
            ]["Default"],
            " ",
        )
        self.assertEqual(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3VersionKey0A652998"
            ]["Default"],
            " ",
        )
        self.assertEqual(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652999"
            ]["Default"],
            "/path",
        )
        self.assertIsNone(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652900"
            ].get("Default")
        )
        self.assertIsNone(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652345"
            ].get("Default")
        )
        self.assertIsNone(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652345123"
            ].get("Default")
        )

    def test_skip_normalizing_already_normalized_resource(self):
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
        self.assertEqual(True, template_data["Resources"]["Function1"]["Metadata"]["SamNormalized"])

        # Normalized resource will not be normalized again
        template_data["Resources"]["Function1"]["Metadata"]["aws:asset:path"] = "updated path"
        ResourceMetadataNormalizer.normalize(template_data)
        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("Function1", template_data["Resources"]["Function1"]["Metadata"]["SamResourceId"])


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
