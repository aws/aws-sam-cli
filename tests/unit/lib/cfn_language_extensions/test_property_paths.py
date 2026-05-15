"""Tests for samcli.lib.cfn_language_extensions.property_paths.

Verifies the small jmespath-aware helpers used across the language-extensions
build- and package-time pipelines, plus the contract that every entry in
``PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES`` round-trips through them.
"""

from unittest import TestCase

from samcli.lib.cfn_language_extensions.models import PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES
from samcli.lib.cfn_language_extensions.property_paths import (
    copy_artifact_properties,
    get_prop_value,
    leaf_prop_name,
    resolve_property_paths,
    set_prop_value,
)


class TestGetPropValue(TestCase):
    def test_flat_key(self):
        self.assertEqual(get_prop_value({"CodeUri": "s3://b/k"}, "CodeUri"), "s3://b/k")

    def test_dotted_key(self):
        props = {"Command": {"ScriptLocation": "s3://b/k.py"}}
        self.assertEqual(get_prop_value(props, "Command.ScriptLocation"), "s3://b/k.py")

    def test_missing_returns_none(self):
        self.assertIsNone(get_prop_value({"CodeUri": "x"}, "Command.ScriptLocation"))


class TestSetPropValue(TestCase):
    def test_flat_key(self):
        props = {"CodeUri": "./src"}
        set_prop_value(props, "CodeUri", "s3://b/k")
        self.assertEqual(props["CodeUri"], "s3://b/k")

    def test_dotted_key_creates_intermediate(self):
        props = {"Command": {"Name": "glueetl"}}
        set_prop_value(props, "Command.ScriptLocation", "s3://b/k.py")
        self.assertEqual(props["Command"]["ScriptLocation"], "s3://b/k.py")
        # Sibling keys preserved.
        self.assertEqual(props["Command"]["Name"], "glueetl")


class TestLeafPropName(TestCase):
    def test_flat_path_returns_self(self):
        self.assertEqual(leaf_prop_name("CodeUri"), "CodeUri")

    def test_dotted_path_returns_leaf(self):
        self.assertEqual(leaf_prop_name("Command.ScriptLocation"), "ScriptLocation")
        self.assertEqual(leaf_prop_name("Code.ImageUri"), "ImageUri")


class TestResolvePropertyPaths(TestCase):
    def test_picks_dotted_child_when_user_uses_image_shape(self):
        # AWS::Lambda::Function: ZIP uses Code, image uses Code.ImageUri.
        # User template has the image shape; resolver must pick the dotted entry.
        props = {"Code": {"ImageUri": "local-tag:latest"}}
        self.assertEqual(resolve_property_paths(["Code", "Code.ImageUri"], props), ["Code.ImageUri"])

    def test_picks_parent_when_user_uses_zip_shape(self):
        # ZIP shape: Code is a string path or {S3Bucket, S3Key} dict — never has ImageUri sub-key.
        props = {"Code": {"S3Bucket": "b", "S3Key": "k"}}
        self.assertEqual(resolve_property_paths(["Code", "Code.ImageUri"], props), ["Code"])

    def test_skips_paths_with_no_value(self):
        self.assertEqual(resolve_property_paths(["CodeUri", "ImageUri"], {"CodeUri": "x"}), ["CodeUri"])

    def test_preserves_input_order_for_unrelated_paths(self):
        props = {"SchemaUri": "s.graphql", "CodeUri": "src/"}
        # Both present; neither is a prefix of the other; order should match input.
        self.assertEqual(
            resolve_property_paths(["SchemaUri", "CodeUri"], props),
            ["SchemaUri", "CodeUri"],
        )


class TestCopyArtifactProperties(TestCase):
    """End-to-end behaviors of the consolidated copy helper.

    The full per-resource-type matrix (Function/Layer/Api/StateMachine/...) is
    in tests/unit/commands/package/test_package_context.py — those tests
    exercise the same call site against the canonical dict.
    """

    def test_copies_flat_property(self):
        original_props = {"CodeUri": "./src"}
        exported_props = {"CodeUri": "s3://b/k"}
        self.assertTrue(copy_artifact_properties(original_props, exported_props, "AWS::Serverless::Function"))
        self.assertEqual(original_props["CodeUri"], "s3://b/k")

    def test_copies_dotted_property_without_clobbering_siblings(self):
        # Glue.Command.ScriptLocation: must land under Properties.Command.ScriptLocation,
        # NOT at a literal "Command.ScriptLocation" flat key.
        original_props = {"Command": {"Name": "glueetl", "ScriptLocation": "./script.py"}}
        exported_props = {"Command": {"Name": "glueetl", "ScriptLocation": "s3://b/k.py"}}
        self.assertTrue(copy_artifact_properties(original_props, exported_props, "AWS::Glue::Job"))
        self.assertEqual(original_props["Command"]["ScriptLocation"], "s3://b/k.py")
        self.assertEqual(original_props["Command"]["Name"], "glueetl")
        self.assertNotIn("Command.ScriptLocation", original_props)

    def test_unknown_resource_type_is_noop(self):
        original_props = {"X": "y"}
        self.assertFalse(copy_artifact_properties(original_props, {"X": "z"}, "AWS::SNS::Topic"))
        # Original was not touched.
        self.assertEqual(original_props["X"], "y")

    def test_dynamic_prop_keys_skip(self):
        # When called from the language-extensions merge path, dynamic
        # (loop-templated) properties are skipped and handled by Mappings.
        original_props = {"CodeUri": "./services/${Name}"}
        exported_props = {"CodeUri": "s3://b/k"}
        result = copy_artifact_properties(
            original_props,
            exported_props,
            "AWS::Serverless::Function",
            foreach_key="Fn::ForEach::Services",
            dynamic_prop_keys={("Fn::ForEach::Services", "CodeUri")},
        )
        self.assertFalse(result)
        # Original was not overwritten — Mapping/FindInMap will replace it later.
        self.assertEqual(original_props["CodeUri"], "./services/${Name}")


class TestPackageablePropertyContract(TestCase):
    """Lock in the structural contract every artifact property must satisfy.

    If a future addition to ``RESOURCES_WITH_LOCAL_PATHS`` /
    ``RESOURCES_WITH_IMAGE_COMPONENT`` declares a property whose path doesn't
    round-trip through ``set_prop_value`` + ``get_prop_value``, or whose leaf
    isn't alphanumeric (it must be, to appear in a CloudFormation Mapping
    name), this test fails loudly at the contract layer rather than at a
    user-template execution path.
    """

    def test_every_packageable_property_round_trips_and_has_alphanumeric_leaf(self):
        for resource_type, paths in PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.items():
            for path in paths:
                with self.subTest(resource_type=resource_type, path=path):
                    # Round trip: write then read.
                    props: dict = {}
                    set_prop_value(props, path, "sentinel")
                    self.assertEqual(
                        get_prop_value(props, path),
                        "sentinel",
                        f"{resource_type}.{path}: set_prop_value/get_prop_value did not round-trip",
                    )
                    # Leaf must be alphanumeric — Mapping names can't contain dots.
                    leaf = leaf_prop_name(path)
                    self.assertTrue(
                        leaf.isalnum(),
                        f"{resource_type}.{path}: leaf {leaf!r} must be alphanumeric "
                        f"(used as Mapping name suffix and FindInMap third arg)",
                    )
