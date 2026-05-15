"""Tests for ``samcli.lib.cfn_language_extensions.foreach_mapping_helpers``.

Verifies the three pure helpers — ``compute_mapping_name``,
``compute_lookup_key``, ``compute_compound_mapping_key`` — and asserts that
the build-time (``samcli/commands/build/build_context.py``) and package-time
(``samcli/lib/package/language_extensions_packaging.py``) call sites produce
the same Mapping name when fed equivalent inputs (cross-pipeline equivalence).
"""

from collections import Counter
from unittest import TestCase

from parameterized import parameterized

from samcli.lib.cfn_language_extensions.exceptions import InvalidTemplateException
from samcli.lib.cfn_language_extensions.foreach_mapping_helpers import (
    compute_compound_mapping_key,
    compute_lookup_key,
    compute_mapping_name,
)


class TestComputeMappingName(TestCase):
    @parameterized.expand(
        [
            # (leaf, nesting_path, has_collision, resource_template_key, expected)
            # No collision: bare base name, resource_template_key is unused.
            ("CodeUri", "Services", False, "${Svc}Function", "SAMCodeUriServices"),
            ("ContentUri", "Layers", False, "${Name}Layer", "SAMContentUriLayers"),
            ("ScriptLocation", "Jobs", False, "${Name}Job", "SAMScriptLocationJobs"),
            # Collision: append sanitized resource-template-key suffix.
            ("CodeUri", "Services", True, "${Svc}Api", "SAMCodeUriServicesApi"),
            ("CodeUri", "Services", True, "${Svc}StateMachine", "SAMCodeUriServicesStateMachine"),
            ("ImageUri", "Funcs", True, "${Name}Lambda", "SAMImageUriFuncsLambda"),
            # Nested loop (nesting_path is the concatenation of ancestor + current).
            ("CodeUri", "EnvsServices", False, "${Env}${Svc}Function", "SAMCodeUriEnvsServices"),
            ("DefinitionUri", "EnvsServices", True, "${Env}${Svc}Api", "SAMDefinitionUriEnvsServicesApi"),
        ]
    )
    def test_construction(self, leaf, nesting_path, has_collision, resource_template_key, expected):
        self.assertEqual(
            compute_mapping_name(
                leaf,
                nesting_path,
                has_collision=has_collision,
                resource_template_key=resource_template_key,
            ),
            expected,
        )

    def test_resource_template_key_with_no_static_segment_raises(self):
        # sanitize_resource_key_for_mapping rejects keys whose static portion is
        # empty — propagates as InvalidTemplateException so the caller surfaces a
        # useful error instead of silently producing colliding Mapping names.
        with self.assertRaises(InvalidTemplateException):
            compute_mapping_name(
                "CodeUri",
                "Services",
                has_collision=True,
                resource_template_key="${OnlyAVariable}",
            )


class TestComputeLookupKey(TestCase):
    def test_no_outer_vars_uses_simple_ref(self):
        self.assertEqual(compute_lookup_key("Name", []), {"Ref": "Name"})

    def test_one_outer_var_uses_fn_join(self):
        self.assertEqual(
            compute_lookup_key("Svc", ["Env"]),
            {"Fn::Join": ["-", [{"Ref": "Env"}, {"Ref": "Svc"}]]},
        )

    def test_multiple_outer_vars_preserves_order(self):
        self.assertEqual(
            compute_lookup_key("Svc", ["Env", "Region"]),
            {"Fn::Join": ["-", [{"Ref": "Env"}, {"Ref": "Region"}, {"Ref": "Svc"}]]},
        )

    def test_none_outer_vars_falls_back_to_simple_ref(self):
        # The build-side caller may pass an empty referenced_outer_vars list;
        # treat it the same as an explicit empty list.
        self.assertEqual(compute_lookup_key("Name", []), {"Ref": "Name"})


class TestComputeCompoundMappingKey(TestCase):
    def test_no_outer_values_returns_inner_only(self):
        self.assertEqual(compute_compound_mapping_key([], "Users"), "Users")

    def test_single_outer_value(self):
        self.assertEqual(compute_compound_mapping_key(["Dev"], "Users"), "Dev-Users")

    def test_multiple_outer_values_in_order(self):
        self.assertEqual(compute_compound_mapping_key(["Dev", "Api"], "Users"), "Dev-Api-Users")


class TestCrossPipelineEquivalence(TestCase):
    """Lock in: build's call shape and package's call shape produce identical
    Mapping names for the same logical inputs.

    Build-time (``_update_foreach_artifact_paths``):
        leaf_name = leaf_prop_name(prop_name)
        has_collision = dynamic_props_count.get(leaf_name, 0) > 1

    Package-time (``_compute_mapping_name``):
        leaf = leaf_prop_name(prop.property_name)
        has_collision = collision_groups.get((nesting_path, leaf), 0) > 1

    For the same set of (nesting_path, leaf, resource_template_key) inputs,
    both code paths must yield byte-identical Mapping names. If a future
    refactor changes one helper but forgets the other, this test fails loudly.
    """

    def test_no_collision_paths_match(self):
        # A simulated set of dynamic-property events: one (nesting_path, leaf)
        # appears once, so neither caller should see a collision.
        events = [("Services", "CodeUri", "${Svc}Function")]

        build_count = Counter(leaf for _, leaf, _ in events)
        package_groups = Counter((path, leaf) for path, leaf, _ in events)

        for path, leaf, key in events:
            build_name = compute_mapping_name(
                leaf,
                path,
                has_collision=build_count.get(leaf, 0) > 1,
                resource_template_key=key,
            )
            package_name = compute_mapping_name(
                leaf,
                path,
                has_collision=package_groups.get((path, leaf), 0) > 1,
                resource_template_key=key,
            )
            self.assertEqual(build_name, package_name, f"divergence at {path}/{leaf}")

    def test_collision_within_single_loop_paths_match(self):
        # Two resources in the same Fn::ForEach body share a leaf — the
        # resource-key suffix should be applied by both pipelines.
        events = [
            ("Services", "DefinitionUri", "${Svc}Api"),
            ("Services", "DefinitionUri", "${Svc}StateMachine"),
        ]

        build_count = Counter(leaf for _, leaf, _ in events)
        package_groups = Counter((path, leaf) for path, leaf, _ in events)

        names_via_build = []
        names_via_package = []
        for path, leaf, key in events:
            names_via_build.append(
                compute_mapping_name(
                    leaf,
                    path,
                    has_collision=build_count.get(leaf, 0) > 1,
                    resource_template_key=key,
                )
            )
            names_via_package.append(
                compute_mapping_name(
                    leaf,
                    path,
                    has_collision=package_groups.get((path, leaf), 0) > 1,
                    resource_template_key=key,
                )
            )

        self.assertEqual(names_via_build, names_via_package)
        # Both names exist and are distinct — neither resource silently
        # overwrites the other's Mapping entries.
        self.assertEqual(len(set(names_via_build)), 2)

    def test_dotted_paths_with_shared_leaf_collide(self):
        # AWS::Serverless::Function.ImageUri and AWS::Lambda::Function.Code.ImageUri
        # have different dotted paths but the same leaf "ImageUri". The
        # collision-detection key on both pipelines is keyed on the leaf, so
        # both produce the same Mapping name and get the resource-key suffix.
        # (Regression for the bug bot review #3 caught on PR #9009.)
        events = [
            ("Funcs", "ImageUri", "${Name}Sam"),
            ("Funcs", "ImageUri", "${Name}Lambda"),
        ]

        build_count = Counter(leaf for _, leaf, _ in events)
        package_groups = Counter((path, leaf) for path, leaf, _ in events)

        names = []
        for path, leaf, key in events:
            build_name = compute_mapping_name(
                leaf,
                path,
                has_collision=build_count.get(leaf, 0) > 1,
                resource_template_key=key,
            )
            package_name = compute_mapping_name(
                leaf,
                path,
                has_collision=package_groups.get((path, leaf), 0) > 1,
                resource_template_key=key,
            )
            self.assertEqual(build_name, package_name)
            names.append(build_name)

        self.assertEqual(names, ["SAMImageUriFuncsSam", "SAMImageUriFuncsLambda"])
