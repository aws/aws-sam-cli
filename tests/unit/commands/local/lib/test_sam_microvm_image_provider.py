"""Unit tests for SamMicrovmImageProvider."""

import os
import posixpath
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.providers.provider import MicrovmImage, Stack
from samcli.lib.providers.sam_microvm_image_provider import SamMicrovmImageProvider


class TestSamMicrovmImageProvider(TestCase):
    TEMPLATE = {
        "Resources": {
            "ServerlessMicrovmImage": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {
                    "Name": "my-app",
                    "CodeUri": "./app",
                    "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                    "BaseImageVersion": "0",
                },
            },
            "ServerlessMicrovmImageWithMetadata": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {
                    "Name": "with-metadata",
                    "CodeUri": "./app3",
                    "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                    "BaseImageVersion": "0",
                },
                "Metadata": {"SkipBuild": True},
            },
            "ServerlessMicrovmImageS3": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {
                    "Name": "s3-app",
                    "CodeUri": "s3://bucket/app.zip",
                    "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                    "BaseImageVersion": "0",
                },
            },
            "LambdaMicrovmImage": {
                "Type": "AWS::Lambda::MicrovmImage",
                "Properties": {
                    "CodeArtifact": "./lambda-app",
                },
            },
            "MicrovmImageWithArch": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {
                    "Name": "arch-app",
                    "CodeUri": "./app-arch",
                    "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                    "BaseImageVersion": "0",
                    "CpuConfigurations": [{"Architecture": "ARM_64"}],
                },
            },
            "SamFunc": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/key",
                    "Runtime": "python3.12",
                    "Handler": "index.handler",
                },
            },
            "ChildStack": {
                "Type": "AWS::Serverless::Application",
                "Properties": {
                    "Location": "./child.yaml",
                },
            },
        }
    }

    CHILD_TEMPLATE = {
        "Resources": {
            "MicrovmImageInChild": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {
                    "Name": "child-app",
                    "CodeUri": "./child-app",
                    "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                    "BaseImageVersion": "0",
                },
            },
        }
    }

    def setUp(self):
        root_stack = Stack("", "", "template.yaml", None, self.TEMPLATE)
        child_stack = Stack("", "ChildStack", "./child/template.yaml", None, self.CHILD_TEMPLATE)
        self.provider = SamMicrovmImageProvider([root_stack, child_stack], use_raw_codeuri=True)

    @parameterized.expand(
        [
            # (lookup name, expected name/logical_id or None)
            ("ServerlessMicrovmImage", "ServerlessMicrovmImage"),  # by logical ID (name field)
            ("my-app", "ServerlessMicrovmImage"),  # by microvm_image_name (Properties.Name)
            ("with-metadata", "ServerlessMicrovmImageWithMetadata"),  # by microvm_image_name
            ("LambdaMicrovmImage", "LambdaMicrovmImage"),  # Lambda type by logical ID
            (posixpath.join("ChildStack", "MicrovmImageInChild"), "MicrovmImageInChild"),  # by full_path
            ("child-app", "MicrovmImageInChild"),  # child stack by microvm_image_name
            ("ServerlessMicrovmImageS3", None),  # S3 CodeUri skipped
            ("SamFunc", None),  # non-microvm resource
            ("NonExistent", None),  # not found
        ]
    )
    def test_get(self, lookup_name, expected_name):
        actual = self.provider.get(lookup_name)
        if expected_name is None:
            self.assertIsNone(actual)
        else:
            self.assertIsNotNone(actual)
            self.assertEqual(actual.name, expected_name)

    def test_get_all_must_return_all_buildable_images(self):
        result = [img.full_path for img in self.provider.get_all()]
        expected = [
            "ServerlessMicrovmImage",
            "ServerlessMicrovmImageWithMetadata",
            "LambdaMicrovmImage",
            "MicrovmImageWithArch",
            posixpath.join("ChildStack", "MicrovmImageInChild"),
        ]
        self.assertEqual(expected, result)

    def test_s3_code_uri_is_excluded(self):
        """S3 CodeUri images should not appear in get_all results."""
        all_names = [img.name for img in self.provider.get_all()]
        self.assertNotIn("ServerlessMicrovmImageS3", all_names)

    def test_non_microvm_resources_are_excluded(self):
        """Non-MicrovmImage resources should not appear in get_all results."""
        all_names = [img.name for img in self.provider.get_all()]
        self.assertNotIn("SamFunc", all_names)
        self.assertNotIn("ChildStack", all_names)

    def test_metadata_is_extracted(self):
        image = self.provider.get("ServerlessMicrovmImageWithMetadata")
        self.assertEqual(image.metadata.get("SkipBuild"), True)

    def test_get_returns_none_for_empty_string(self):
        self.assertIsNone(self.provider.get(""))

    def test_child_stack_image_has_correct_stack_path(self):
        image = self.provider.get("child-app")
        self.assertEqual(image.stack_path, "ChildStack")
        self.assertEqual(image.full_path, posixpath.join("ChildStack", "MicrovmImageInChild"))

    def test_architecture_extracted_from_cpu_configurations(self):
        image = self.provider.get("MicrovmImageWithArch")
        self.assertEqual(image.architecture, "arm64")

    def test_architecture_defaults_to_arm64_when_not_specified(self):
        image = self.provider.get("ServerlessMicrovmImage")
        self.assertEqual(image.architecture, "arm64")

    @parameterized.expand(
        [
            # (CodeArtifact value, expected code_uri or None if skipped)
            ("bare string from CDK normalize", "./lambda-app", "./lambda-app"),
            ("nested local Uri", {"Uri": "./lambda-app"}, "./lambda-app"),
            ("nested S3 Uri", {"Uri": "s3://bucket/app.zip"}, None),
        ]
    )
    def test_lambda_microvm_image_code_artifact_forms(self, _name, code_artifact, expected_code_uri):
        stack = Stack(
            "",
            "",
            "template.yaml",
            None,
            {
                "Resources": {
                    "Img": {"Type": "AWS::Lambda::MicrovmImage", "Properties": {"CodeArtifact": code_artifact}}
                }
            },
        )
        image = SamMicrovmImageProvider([stack], use_raw_codeuri=True).get("Img")
        if expected_code_uri is None:
            self.assertIsNone(image)
        else:
            self.assertEqual(image.code_uri, expected_code_uri)

    def test_get_prefers_logical_id_over_another_images_name(self):
        """One image's Properties.Name must not shadow another image's logical ID."""
        stack = Stack(
            "",
            "",
            "template.yaml",
            None,
            {
                "Resources": {
                    "ImageA": {
                        "Type": "AWS::Serverless::MicrovmImage",
                        "Properties": {
                            "Name": "ImageB",
                            "CodeUri": "./a",
                            "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                            "BaseImageVersion": "0",
                        },
                    },
                    "ImageB": {
                        "Type": "AWS::Serverless::MicrovmImage",
                        "Properties": {
                            "Name": "SomethingElse",
                            "CodeUri": "./b",
                            "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                            "BaseImageVersion": "0",
                        },
                    },
                }
            },
        )
        provider = SamMicrovmImageProvider([stack], use_raw_codeuri=True)
        self.assertEqual(provider.get("ImageB").code_uri, "./b")
        self.assertEqual(provider.get("SomethingElse").name, "ImageB")

    def test_get_skip_reason_for_skipped_images(self):
        stack = Stack(
            "",
            "",
            "template.yaml",
            None,
            {
                "Resources": {
                    "S3Image": {
                        "Type": "AWS::Serverless::MicrovmImage",
                        "Properties": {
                            "Name": "s3-image",
                            "CodeUri": "s3://bucket/app.zip",
                            "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                            "BaseImageVersion": "0",
                        },
                    },
                    "BadImage": {"Type": "AWS::Lambda::MicrovmImage", "Properties": {"CodeArtifact": {"Uri": 5}}},
                    "GoodImage": {"Type": "AWS::Lambda::MicrovmImage", "Properties": {"CodeArtifact": "./app"}},
                }
            },
        )
        provider = SamMicrovmImageProvider([stack], use_raw_codeuri=True)

        for identifier in ("S3Image", "s3-image"):
            self.assertIsNone(provider.get(identifier))
            self.assertIn("CodeUri is an S3 location", provider.get_skip_reason(identifier))
        self.assertIn("CodeArtifact is missing or invalid", provider.get_skip_reason("BadImage"))
        self.assertIsNone(provider.get_skip_reason("GoodImage"))
        self.assertIsNone(provider.get_skip_reason("NonExistent"))

    def test_ignore_code_extraction_warnings_skips_warning(self):
        stack = Stack(
            "",
            "",
            "template.yaml",
            None,
            {
                "Resources": {
                    "MyImage": {
                        "Type": "AWS::Serverless::MicrovmImage",
                        "Properties": {
                            "Name": "my-image",
                            "CodeUri": "s3://bucket/app.zip",
                            "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                            "BaseImageVersion": "0",
                        },
                    }
                }
            },
        )
        provider = SamMicrovmImageProvider([stack], ignore_code_extraction_warnings=True)
        self.assertEqual(provider.get_all(), [])

    def test_code_uri_normalized_relative_to_template_location(self):
        stack = Stack(
            "",
            "",
            os.path.join("some", "dir", "template.yaml"),
            None,
            {
                "Resources": {
                    "MyImage": {
                        "Type": "AWS::Serverless::MicrovmImage",
                        "Properties": {
                            "Name": "my-image",
                            "CodeUri": "./app",
                            "BaseImageArn": "arn:aws:lambda:::microvm-image:base",
                            "BaseImageVersion": "0",
                        },
                    }
                }
            },
        )
        provider = SamMicrovmImageProvider([stack], use_raw_codeuri=False)
        image = provider.get("MyImage")
        self.assertEqual(image.code_uri, os.path.join("some", "dir", "app"))
