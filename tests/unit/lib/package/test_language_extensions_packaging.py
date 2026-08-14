"""Unit tests for samcli.lib.package.language_extensions_packaging.

Resource-property merge tests live in test_artifact_exporter.py; this file
focuses on the Metadata merge pass added for the registry-driven merge.
"""

from unittest import TestCase

from samcli.lib.package.language_extensions_packaging import merge_language_extensions_s3_uris


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
