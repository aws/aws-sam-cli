"""Unit tests for samcli.lib.package.language_extensions_packaging.

Resource-property merge tests live in test_artifact_exporter.py; this file
focuses on the Metadata merge pass added for the registry-driven merge.
"""

import copy
from unittest import TestCase

from samcli.lib.package.language_extensions_packaging import (
    merge_language_extensions_s3_uris,
    wrap_microvm_image_code_artifact_strings,
)


class TestMergeMetadata(TestCase):
    def test_serverless_repo_license_url_is_merged(self):
        original = {
            "Transform": "AWS::LanguageExtensions",
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "MyApp",
                    "LicenseUrl": "./LICENSE.txt",
                    "ReadmeUrl": "./README.md",
                }
            },
            "Resources": {},
        }
        exported = {
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "MyApp",
                    "LicenseUrl": "s3://bucket/license-md5",
                    "ReadmeUrl": "s3://bucket/readme-md5",
                }
            },
            "Resources": {},
        }

        result = merge_language_extensions_s3_uris(original, exported)

        sar = result["Metadata"]["AWS::ServerlessRepo::Application"]
        self.assertEqual(sar["LicenseUrl"], "s3://bucket/license-md5")
        self.assertEqual(sar["ReadmeUrl"], "s3://bucket/readme-md5")
        self.assertEqual(sar["Name"], "MyApp")  # unrelated keys preserved

    def test_metadata_without_serverless_repo_is_unchanged(self):
        original = {
            "Metadata": {"OtherKey": {"Foo": "./bar"}},
            "Resources": {},
        }
        exported = {
            "Metadata": {"OtherKey": {"Foo": "./bar"}},
            "Resources": {},
        }

        result = merge_language_extensions_s3_uris(original, exported)

        self.assertEqual(result["Metadata"], {"OtherKey": {"Foo": "./bar"}})

    def test_missing_metadata_section_in_either_template_is_safe(self):
        # No Metadata in original
        result = merge_language_extensions_s3_uris(
            {"Resources": {}},
            {"Metadata": {"AWS::ServerlessRepo::Application": {"LicenseUrl": "s3://x"}}, "Resources": {}},
        )
        self.assertNotIn("Metadata", result)

        # No Metadata in exported
        original = {
            "Metadata": {"AWS::ServerlessRepo::Application": {"LicenseUrl": "./LICENSE"}},
            "Resources": {},
        }
        result = merge_language_extensions_s3_uris(original, {"Resources": {}})
        # Original retained, since exporter never wrote anything
        self.assertEqual(result["Metadata"]["AWS::ServerlessRepo::Application"]["LicenseUrl"], "./LICENSE")

    def test_partial_serverless_repo_export_preserves_unwritten_properties(self):
        """If the exported template has only LicenseUrl written (no ReadmeUrl),
        the original's ReadmeUrl must be left untouched. Guards the
        `if prop_name in exported_entry:` check in _merge_metadata.
        """
        original = {
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "MyApp",
                    "LicenseUrl": "./LICENSE.txt",
                    "ReadmeUrl": "./README.md",
                }
            },
            "Resources": {},
        }
        exported = {
            "Metadata": {
                "AWS::ServerlessRepo::Application": {
                    "Name": "MyApp",
                    "LicenseUrl": "s3://bucket/license-md5",
                    # ReadmeUrl deliberately absent
                }
            },
            "Resources": {},
        }

        result = merge_language_extensions_s3_uris(original, exported)

        sar = result["Metadata"]["AWS::ServerlessRepo::Application"]
        self.assertEqual(sar["LicenseUrl"], "s3://bucket/license-md5")
        self.assertEqual(sar["ReadmeUrl"], "./README.md")  # untouched


class TestWrapMicrovmImageCodeArtifactStrings(TestCase):
    """A string CodeArtifact is wrapped as {Uri: ...} so a Fn::ForEach body matches the exported shape."""

    @staticmethod
    def _image(code_artifact, resource_type="AWS::Lambda::MicrovmImage"):
        return {"Type": resource_type, "Properties": {"CodeArtifact": code_artifact}}

    def test_wraps_local_strings_at_top_level_and_in_nested_foreach(self):
        template = {
            "Resources": {
                "Plain": self._image("./app"),
                "Fn::ForEach::Outer": [
                    "N",
                    ["Alpha", "Beta"],
                    {
                        "${N}Image": self._image("./${N}"),
                        "Fn::ForEach::Inner": ["M", ["X"], {"${N}${M}Image": self._image("./${N}/${M}")}],
                    },
                ],
            }
        }

        wrap_microvm_image_code_artifact_strings(template)

        resources = template["Resources"]
        outer_body = resources["Fn::ForEach::Outer"][2]
        self.assertEqual(resources["Plain"]["Properties"]["CodeArtifact"], {"Uri": "./app"})
        self.assertEqual(outer_body["${N}Image"]["Properties"]["CodeArtifact"], {"Uri": "./${N}"})
        self.assertEqual(
            outer_body["Fn::ForEach::Inner"][2]["${N}${M}Image"]["Properties"]["CodeArtifact"], {"Uri": "./${N}/${M}"}
        )

    def test_leaves_other_values_and_resource_types_unchanged(self):
        unchanged = {
            "OnS3": self._image("s3://bucket/app.zip"),
            "UriForm": self._image({"Uri": "./app"}),
            "Intrinsic": self._image({"Fn::Sub": "./${Env}"}),
            "Function": {"Type": "AWS::Lambda::Function", "Properties": {"Code": "./app"}},
            "SamImage": {"Type": "AWS::Serverless::MicrovmImage", "Properties": {"CodeUri": "./app"}},
        }
        template = {"Resources": copy.deepcopy(unchanged)}

        wrap_microvm_image_code_artifact_strings(template)

        self.assertEqual(template["Resources"], unchanged)
