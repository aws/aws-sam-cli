"""Unit tests for samcli.lib.package.language_extensions_packaging.

Resource-property merge tests live in test_artifact_exporter.py; this file
focuses on the Metadata merge pass added for the registry-driven merge.
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.package.language_extensions_packaging import (
    merge_language_extensions_s3_uris,
    warn_parameter_based_collections,
)


class TestWarnParameterBasedCollections(TestCase):
    @staticmethod
    def _param_ref_property():
        return Mock(
            collection_is_parameter_ref=True,
            foreach_key="Fn::ForEach::Loop",
            loop_name="Loop",
            collection_parameter_name="MyParam",
            property_name="CodeUri",
        )

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_defaults_to_stdout(self, patched_click):
        warn_parameter_based_collections([self._param_ref_property()])

        patched_click.secho.assert_called_once()
        # Default (e.g. sam package) writes to stdout.
        self.assertFalse(patched_click.secho.call_args.kwargs.get("err", False))

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_routes_to_stderr_when_requested(self, patched_click):
        # JSON-mode callers pass to_stderr=True so the warning never corrupts the JSON stream.
        warn_parameter_based_collections([self._param_ref_property()], to_stderr=True)

        patched_click.secho.assert_called_once()
        self.assertTrue(patched_click.secho.call_args.kwargs.get("err"))


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
