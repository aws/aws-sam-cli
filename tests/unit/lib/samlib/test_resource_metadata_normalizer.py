import pathlib
from unittest import TestCase

from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer


class TestResourceMeatadataNormalizer(TestCase):
    def test_replace_property_with_path(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {"Code": "some value"},
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
                    "Properties": {"Code": "some value"},
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                },
                "Resource2": {
                    "Properties": {"SomeRandomProperty": "some value"},
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
                            "ImageUri": "Some Value",
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
                            "ImageUri": "Some Value",
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
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652998": {
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
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash": {
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
            },
        }

        ResourceMetadataNormalizer.normalize(template_data, True)
        self.assertEquals(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash0A652998"
            ]["Default"],
            " ",
        )
        self.assertEquals(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3Bucket0A652998"
            ]["Default"],
            " ",
        )
        self.assertEquals(
            template_data["Parameters"][
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3VersionKey0A652998"
            ]["Default"],
            " ",
        )
        self.assertEquals(
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
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481ArtifactHash"
            ].get("Default")
        )
