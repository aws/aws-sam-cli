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
