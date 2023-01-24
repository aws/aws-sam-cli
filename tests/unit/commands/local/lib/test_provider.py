import os
import posixpath
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from parameterized import parameterized, parameterized_class

from samcli.lib.utils.architecture import X86_64, ARM64

from samcli.lib.providers.provider import (
    LayerVersion,
    ResourceIdentifier,
    Stack,
    _get_build_dir,
    get_all_resource_ids,
    get_resource_by_id,
    get_resource_ids_by_type,
    get_unique_resource_ids,
    Function,
    get_resource_full_path_by_id,
)
from samcli.commands.local.cli_common.user_exceptions import (
    InvalidLayerVersionArn,
    UnsupportedIntrinsic,
    InvalidFunctionPropertyType,
)


def make_resource(stack_path, name):
    resource = Mock()
    resource.stack_path = stack_path
    resource.name = name
    return resource


class TestProvider(TestCase):
    @parameterized.expand(
        [
            (make_resource("", "A"), os.path.join("builddir", "A")),
            (make_resource("A", "B"), os.path.join("builddir", "A", "B")),
            (make_resource("A/B", "C"), os.path.join("builddir", "A", "B", "C")),
        ]
    )
    def test_stack_build_dir(self, resource, output_build_dir):
        self.assertEqual(_get_build_dir(resource, "builddir"), output_build_dir)

    @parameterized.expand(
        [
            ("", "", os.path.join("builddir", "template.yaml")),  # root stack
            ("", "A", os.path.join("builddir", "A", "template.yaml")),
            ("A", "B", os.path.join("builddir", "A", "B", "template.yaml")),
            ("A/B", "C", os.path.join("builddir", "A", "B", "C", "template.yaml")),
        ]
    )
    def test_stack_get_output_template_path(self, parent_stack_path, name, output_template_path):
        root_stack = Stack(parent_stack_path, name, None, None, None, None)
        self.assertEqual(root_stack.get_output_template_path("builddir"), output_template_path)


@parameterized_class(
    ("stack", "expected_id", "expected_stack_path"),
    [
        (
            # empty metadata
            Stack("", "stackLogicalId", "/stack", None, {}, {}),
            "stackLogicalId",
            "stackLogicalId",
        ),
        (
            # None metadata
            Stack("", "stackLogicalId", "/stack", None, {}, None),
            "stackLogicalId",
            "stackLogicalId",
        ),
        (
            # metadata without sam resource id
            Stack("", "stackLogicalId", "/stack", None, {}, {"id": "id"}),
            "stackLogicalId",
            "stackLogicalId",
        ),
        (
            # metadata with sam resource id
            Stack("", "stackLogicalId", "/stack", None, {}, {"SamResourceId": "stackCustomId"}),
            "stackCustomId",
            "stackCustomId",
        ),
        (
            # empty metadata
            Stack("stack", "stackLogicalId", "/stack", None, {}, {}),
            "stackLogicalId",
            posixpath.join("stack", "stackLogicalId"),
        ),
        (
            # None metadata
            Stack("stack", "stackLogicalId", "/stack", None, {}, None),
            "stackLogicalId",
            posixpath.join("stack", "stackLogicalId"),
        ),
        (
            # metadata without sam resource id
            Stack("stack", "stackLogicalId", "/stack", None, {}, {"id": "id"}),
            "stackLogicalId",
            posixpath.join("stack", "stackLogicalId"),
        ),
        (
            # metadata with sam resource id
            Stack("stack", "stackLogicalId", "/stack", None, {}, {"SamResourceId": "stackCustomId"}),
            "stackCustomId",
            posixpath.join("stack", "stackCustomId"),
        ),
    ],
)
class TestStack(TestCase):
    stack = None
    expected_id = None
    expected_stack_path = None

    def test_stack_id(self):
        self.assertEqual(self.expected_id, self.stack.stack_id)

    def test_stack_path(self):
        self.assertEqual(self.expected_stack_path, self.stack.stack_path)


class TestStackEqual(TestCase):
    def test_stacks_are_equal(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        stack2 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        self.assertTrue(stack1 == stack2)

    def test_stacks_are_not_equal_different_types(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        not_stack = Mock()
        self.assertFalse(stack1 == not_stack)

    def test_stacks_are_not_equal_different_parent_stack_path(self):
        stack1 = Stack(
            "stack1",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        stack2 = Stack(
            "stack2",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        self.assertFalse(stack1 == stack2)

    def test_stacks_are_not_equal_different_stack_name(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId1",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        stack2 = Stack(
            "stack",
            "stackLogicalId2",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        self.assertFalse(stack1 == stack2)

    def test_stacks_are_not_equal_different_template_path(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId",
            "/stack1",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        stack2 = Stack(
            "stack",
            "stackLogicalId",
            "/stack2",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        self.assertFalse(stack1 == stack2)

    def test_stacks_are_not_equal_different_parameters(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key1": "value1"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        stack2 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key2": "value2"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        self.assertFalse(stack1 == stack2)

    def test_stacks_are_not_equal_different_templates(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId": "stackCustomId"},
        )
        stack2 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func2": {"Runtime": "Java"}}},
            {"SamResourceId": "stackCustomId"},
        )
        self.assertFalse(stack1 == stack2)

    def test_stacks_are_not_equal_different_metadata(self):
        stack1 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId1": "stackCustomId1"},
        )
        stack2 = Stack(
            "stack",
            "stackLogicalId",
            "/stack",
            {"key": "value"},
            {"Resources": {"func1": {"Runtime": "Python"}}},
            {"SamResourceId2": "stackCustomId2"},
        )
        self.assertFalse(stack1 == stack2)


class TestFunction(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.function = Function(
            "name",
            "name",
            "functionname",
            "runtime",
            10,
            3,
            "handler",
            "imageuri",
            "packagetype",
            "imageconfig",
            "codeuri",
            None,
            "rolearn",
            [],
            None,
            None,
            None,
            None,
            [ARM64],
            None,
            "stackpath",
            None,
        )

    @parameterized.expand(
        [
            ([ARM64], ARM64),
            ([], X86_64),
            ([X86_64], X86_64),
        ]
    )
    def test_architecture(self, architectures, architecture):
        self.function = self.function._replace(architectures=architectures)
        self.assertEqual(self.function.architecture, architecture)

    def test_invalid_architecture(self):
        self.function = self.function._replace(architectures=[X86_64, ARM64])
        with self.assertRaises(InvalidFunctionPropertyType) as e:
            self.function.architecture
        self.assertEqual(str(e.exception), "Function name property Architectures should be a list of length 1")

    def test_skip_build_is_false_if_metadata_is_None(self):
        self.assertFalse(self.function.skip_build)

    def test_skip_build_is_false_if_metadata_is_empty(self):
        self.function = self.function._replace(metadata={})
        self.assertFalse(self.function.skip_build)

    def test_skip_build_is_false_if_skip_build_metadata_flag_is_false(self):
        self.function = self.function._replace(metadata={"SkipBuild": False})
        self.assertFalse(self.function.skip_build)

    def test_skip_build_is_false_if_skip_build_metadata_flag_is_true(self):
        self.function = self.function._replace(metadata={"SkipBuild": True})
        self.assertTrue(self.function.skip_build)


class TestLayerVersion(TestCase):
    @parameterized.expand(
        [
            ("arn:aws:lambda:region:account-id:layer:layer-name:a"),
            ("arn:aws:lambda:region:account-id:layer"),
            ("a string without delimiter"),
        ]
    )
    def test_invalid_arn(self, arn):
        layer = LayerVersion(arn, None)  # creation of layer does not raise exception
        with self.assertRaises(InvalidLayerVersionArn):
            layer.version, layer.name

    def test_layer_version_returned(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.version, 1)

    def test_layer_version_id_is_layer_name_if_no_custom_resource_id(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.layer_id, layer_version.name)

    def test_layer_version_id_is_custom_id_if_custom_resource_id_exist(self):
        layer_version = LayerVersion(
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            None,
            [],
            {"BuildMethod": "dummy_build_method", "SamResourceId": "CustomLayerId"},
        )
        self.assertNotEqual(layer_version.layer_id, layer_version.name)
        self.assertEqual(layer_version.layer_id, "CustomLayerId")

    def test_layer_arn_returned(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.layer_arn, "arn:aws:lambda:region:account-id:layer:layer-name")

    def test_layer_build_method_returned(self):
        layer_version = LayerVersion(
            "arn:aws:lambda:region:account-id:layer:layer-name:1", None, [], {"BuildMethod": "dummy_build_method"}
        )

        self.assertEqual(layer_version.build_method, "dummy_build_method")

    def test_codeuri_is_setable(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)
        layer_version.codeuri = "./some_value"

        self.assertEqual(layer_version.codeuri, "./some_value")

    def test_name_is_computed(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)

        self.assertEqual(layer_version.name, "layer-name-1-8cebcd0539")

    def test_layer_version_is_defined_in_template(self):
        layer_version = LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", ".")

        self.assertTrue(layer_version.is_defined_within_template)

    def test_layer_version_raises_unsupported_intrinsic(self):
        intrinsic_arn = {
            "Fn::Sub": ["arn:aws:lambda:region:account-id:layer:{layer_name}:1", {"layer_name": "layer-name"}]
        }

        with self.assertRaises(UnsupportedIntrinsic):
            LayerVersion(intrinsic_arn, ".")

    def test_compatible_architectures_returned(self):
        layer_version = LayerVersion(
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            None,
            [],
            {"BuildMethod": "dummy_build_method"},
            [ARM64],
        )

        self.assertEqual(layer_version.compatible_architectures, [ARM64])

    def test_layer_build_architecture_returned(self):
        layer_version = LayerVersion(
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            None,
            [],
            {"BuildMethod": "dummy_build_method", "BuildArchitecture": ARM64},
            [ARM64],
        )
        self.assertEqual(layer_version.build_architecture, ARM64)

    def test_no_layer_build_architecture_returned(self):
        layer_version = LayerVersion(
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            None,
            [],
            {"BuildMethod": "dummy_build_method"},
            [ARM64],
        )
        self.assertEqual(layer_version.build_architecture, X86_64)


class TestResourceIdentifier(TestCase):
    @parameterized.expand(
        [
            ("Function1", "", "Function1"),
            ("NestedStack1/Function1", "NestedStack1", "Function1"),
            ("NestedStack1/NestedNestedStack2/Function1", "NestedStack1/NestedNestedStack2", "Function1"),
            ("", "", ""),
        ]
    )
    def test_parser(self, resource_identifier_string, stack_path, logical_id):
        resource_identifier = ResourceIdentifier(resource_identifier_string)
        self.assertEqual(resource_identifier.stack_path, stack_path)
        self.assertEqual(resource_identifier.resource_iac_id, logical_id)

    @parameterized.expand(
        [
            ("Function1", "Function1", True),
            ("NestedStack1/Function1", "NestedStack1/Function1", True),
            ("NestedStack1/NestedNestedStack2/Function1", "NestedStack1/NestedNestedStack2/Function2", False),
            ("NestedStack1/NestedNestedStack3/Function1", "NestedStack1/NestedNestedStack2/Function1", False),
            ("", "", True),
        ]
    )
    def test_equal(self, resource_identifier_string_1, resource_identifier_string_2, equal):
        resource_identifier_1 = ResourceIdentifier(resource_identifier_string_1)
        resource_identifier_2 = ResourceIdentifier(resource_identifier_string_2)
        self.assertEqual(resource_identifier_1 == resource_identifier_2, equal)

    @parameterized.expand(
        [
            ("Function1"),
            ("NestedStack1/Function1"),
            ("NestedStack1/NestedNestedStack2/Function1"),
        ]
    )
    def test_hash(self, resource_identifier_string):
        resource_identifier_1 = ResourceIdentifier(resource_identifier_string)
        resource_identifier_2 = ResourceIdentifier(resource_identifier_string)
        self.assertEqual(hash(resource_identifier_1), hash(resource_identifier_2))

    @parameterized.expand(
        [
            ("Function1"),
            ("NestedStack1/Function1"),
            ("NestedStack1/NestedNestedStack2/Function1"),
            (""),
        ]
    )
    def test_str(self, resource_identifier_string):
        resource_identifier = ResourceIdentifier(resource_identifier_string)
        self.assertEqual(str(resource_identifier), resource_identifier_string)


@parameterized_class(["is_cdk"], [[False], [True]])
class TestGetResourceByID(TestCase):
    is_cdk = False

    def setUp(self) -> None:
        super().setUp()
        self.root_stack = MagicMock()
        self.root_stack.stack_path = ""
        self.root_stack.resources = {"Function1": {"Properties": "Body1"}}
        if self.is_cdk:
            self.root_stack.resources["Function1"]["Metadata"] = {"SamResourceId": "CDKFunction1"}

        self.nested_stack = MagicMock()
        self.nested_stack.stack_path = "NestedStack1"
        self.nested_stack.resources = {"Function1": {"Properties": "Body2"}}
        if self.is_cdk:
            self.nested_stack.resources["Function1"]["Metadata"] = {"SamResourceId": "CDKFunction1"}

        self.nested_nested_stack = MagicMock()
        self.nested_nested_stack.stack_path = "NestedStack1/NestedNestedStack1"
        self.nested_nested_stack.resources = {"Function2": {"Properties": "Body3"}}
        if self.is_cdk:
            self.nested_nested_stack.resources["Function2"]["Metadata"] = {"SamResourceId": "CDKFunction2"}

    def test_get_resource_by_id_explicit_root(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.stack_path = ""
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function1"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, True
        )
        self.assertEqual(result, self.root_stack.resources["Function1"])

        if self.is_cdk:
            # check that logical id also works as resource if
            resource_identifier.resource_iac_id = "Function1"
            result = get_resource_by_id(
                [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, True
            )
            self.assertEqual(result, self.root_stack.resources["Function1"])

    def test_get_resource_by_id_explicit_nested(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.stack_path = "NestedStack1"
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function1"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, True
        )
        self.assertEqual(result, self.nested_stack.resources["Function1"])

    def test_get_resource_by_id_explicit_nested_nested(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.stack_path = "NestedStack1/NestedNestedStack1"
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function2"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, True
        )
        self.assertEqual(result, self.nested_nested_stack.resources["Function2"])

    def test_get_resource_by_id_implicit_root(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.stack_path = ""
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function1"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, False
        )
        self.assertEqual(result, self.root_stack.resources["Function1"])

    def test_get_resource_by_id_implicit_nested(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.stack_path = ""
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function2"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, False
        )
        self.assertEqual(result, self.nested_nested_stack.resources["Function2"])

    def test_get_resource_by_id_implicit_with_stack_path(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.stack_path = "NestedStack1"
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function1"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, False
        )
        self.assertEqual(result, self.nested_stack.resources["Function1"])

    def test_get_resource_by_id_not_found(
        self,
    ):

        resource_identifier = MagicMock()
        resource_identifier.resource_iac_id = f"{'CDK' if self.is_cdk else ''}Function3"

        result = get_resource_by_id(
            [self.root_stack, self.nested_stack, self.nested_nested_stack], resource_identifier, False
        )
        self.assertEqual(result, None)


class TestGetResourceIDsByType(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root_stack = MagicMock()
        self.root_stack.stack_path = ""
        self.root_stack.resources = {
            "Function1": {"Type": "TypeA"},
            "CDKFunction1": {"Type": "TypeA", "Metadata": {"SamResourceId": "CDKFunction1-x"}},
        }

        self.nested_stack = MagicMock()
        self.nested_stack.stack_path = "NestedStack1"
        self.nested_stack.resources = {
            "Function1": {"Type": "TypeA"},
            "CDKFunction1": {"Type": "TypeA", "Metadata": {"SamResourceId": "CDKFunction1-x"}},
        }

        self.nested_nested_stack = MagicMock()
        self.nested_nested_stack.stack_path = "NestedStack1/NestedNestedStack1"
        self.nested_nested_stack.resources = {
            "Function2": {"Type": "TypeB"},
            "CDKFunction2": {"Type": "TypeC", "Metadata": {"SamResourceId": "CDKFunction2-x"}},
        }

    def test_get_resource_ids_by_type_single_nested(
        self,
    ):
        result = get_resource_ids_by_type([self.root_stack, self.nested_stack, self.nested_nested_stack], "TypeB")
        self.assertEqual(result, [ResourceIdentifier("NestedStack1/NestedNestedStack1/Function2")])

    def test_get_resource_ids_by_type_single_cdk_nested(
        self,
    ):
        result = get_resource_ids_by_type([self.root_stack, self.nested_stack, self.nested_nested_stack], "TypeC")
        self.assertEqual(result, [ResourceIdentifier("NestedStack1/NestedNestedStack1/CDKFunction2-x")])

    def test_get_resource_ids_by_type_multiple_nested(
        self,
    ):
        result = get_resource_ids_by_type([self.root_stack, self.nested_stack, self.nested_nested_stack], "TypeA")
        self.assertEqual(
            result,
            [
                ResourceIdentifier("Function1"),
                ResourceIdentifier("CDKFunction1-x"),
                ResourceIdentifier("NestedStack1/Function1"),
                ResourceIdentifier("NestedStack1/CDKFunction1-x"),
            ],
        )


class TestGetAllResourceIDs(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.root_stack = MagicMock()
        self.root_stack.stack_path = ""
        self.root_stack.resources = {
            "Function1": {"Type": "TypeA"},
            "CDKFunction1": {"Type": "TypeA", "Metadata": {"SamResourceId": "CDKFunction1-x"}},
        }

        self.nested_stack = MagicMock()
        self.nested_stack.stack_path = "NestedStack1"
        self.nested_stack.resources = {
            "Function1": {"Type": "TypeA"},
            "CDKFunction1": {"Type": "TypeA", "Metadata": {"SamResourceId": "CDKFunction1-x"}},
        }

        self.nested_nested_stack = MagicMock()
        self.nested_nested_stack.stack_path = "NestedStack1/NestedNestedStack1"
        self.nested_nested_stack.resources = {
            "Function2": {"Type": "TypeB"},
            "CDKFunction2": {"Type": "TypeC", "Metadata": {"SamResourceId": "CDKFunction2-x"}},
        }

    def test_get_all_resource_ids(
        self,
    ):
        result = get_all_resource_ids([self.root_stack, self.nested_stack, self.nested_nested_stack])
        self.assertEqual(
            result,
            [
                ResourceIdentifier("Function1"),
                ResourceIdentifier("CDKFunction1-x"),
                ResourceIdentifier("NestedStack1/Function1"),
                ResourceIdentifier("NestedStack1/CDKFunction1-x"),
                ResourceIdentifier("NestedStack1/NestedNestedStack1/Function2"),
                ResourceIdentifier("NestedStack1/NestedNestedStack1/CDKFunction2-x"),
            ],
        )


class TestGetUniqueResourceIDs(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stacks = MagicMock()

    @patch("samcli.lib.providers.provider.get_resource_ids_by_type")
    def test_only_resource_ids(self, get_resource_ids_by_type_mock):
        resource_ids = ["Function1", "Function2"]
        resource_types = []
        get_resource_ids_by_type_mock.return_value = {}
        result = get_unique_resource_ids(self.stacks, resource_ids, resource_types)
        get_resource_ids_by_type_mock.assert_not_called()
        self.assertEqual(result, {ResourceIdentifier("Function1"), ResourceIdentifier("Function2")})

    @patch("samcli.lib.providers.provider.get_resource_ids_by_type")
    def test_only_resource_types(self, get_resource_ids_by_type_mock):
        resource_ids = []
        resource_types = ["Type1", "Type2"]
        get_resource_ids_by_type_mock.return_value = {ResourceIdentifier("Function1"), ResourceIdentifier("Function2")}
        result = get_unique_resource_ids(self.stacks, resource_ids, resource_types)
        get_resource_ids_by_type_mock.assert_any_call(self.stacks, "Type1")
        get_resource_ids_by_type_mock.assert_any_call(self.stacks, "Type2")
        self.assertEqual(result, {ResourceIdentifier("Function1"), ResourceIdentifier("Function2")})

    @patch("samcli.lib.providers.provider.get_resource_ids_by_type")
    def test_duplicates(self, get_resource_ids_by_type_mock):
        resource_ids = ["Function1", "Function2"]
        resource_types = ["Type1", "Type2"]
        get_resource_ids_by_type_mock.return_value = {ResourceIdentifier("Function2"), ResourceIdentifier("Function3")}
        result = get_unique_resource_ids(self.stacks, resource_ids, resource_types)
        get_resource_ids_by_type_mock.assert_any_call(self.stacks, "Type1")
        get_resource_ids_by_type_mock.assert_any_call(self.stacks, "Type2")
        self.assertEqual(
            result, {ResourceIdentifier("Function1"), ResourceIdentifier("Function2"), ResourceIdentifier("Function3")}
        )


class TestGetResourceFullPathByID(TestCase):
    def setUp(self):
        self.stacks = [
            Stack(
                "",
                "",
                "template.yaml",
                {},
                {
                    "Resources": {
                        "CDKResource1": {
                            "Properties": {"Body"},
                            "Metadata": {
                                "SamResource": "CDKResource1-x",
                                "aws:cdk:path": "Stack/CDKResource1-x/Resource",
                            },
                        },
                        "CFNResource1": {
                            "Properties": {"Body"},
                        },
                    }
                },
            ),
            Stack(
                "",
                "childStack",
                "childStack/template.yaml",
                {},
                {
                    "Resources": {
                        "CDKResourceInChild1": {
                            "Metadata": {
                                "SamResource": "CDKResourceInChild1-x",
                                "aws:cdk:path": "Stack/CDKResourceInChild1-x/Resource",
                            },
                        },
                        "CFNResourceInChild1": {
                            "Properties": {"Body"},
                        },
                    }
                },
            ),
        ]

    @parameterized.expand(
        [
            (ResourceIdentifier("CFNResource1"), "CFNResource1"),
            (ResourceIdentifier("CDKResource1"), "CDKResource1-x"),
            (ResourceIdentifier("CDKResource1-x"), "CDKResource1-x"),
            (ResourceIdentifier("CFNResourceInChild1"), "childStack/CFNResourceInChild1"),
            (ResourceIdentifier("childStack/CFNResourceInChild1"), "childStack/CFNResourceInChild1"),
            (ResourceIdentifier("CDKResourceInChild1"), "childStack/CDKResourceInChild1-x"),
            (ResourceIdentifier("CDKResourceInChild1-x"), "childStack/CDKResourceInChild1-x"),
            (ResourceIdentifier("childStack/CDKResourceInChild1-x"), "childStack/CDKResourceInChild1-x"),
            (ResourceIdentifier("InvalidResourceId"), None),
            (ResourceIdentifier("InvalidStackId/CFNResourceInChild1"), None),
            # we should use iac_resource_id to define full path, could not use resource logical id in full path although
            # cdk id is there
            (ResourceIdentifier("childStack/CDKResourceInChild1"), None),
        ]
    )
    def test_get_resource_full_path_by_id(self, resource_id, expected_full_path):
        full_path = get_resource_full_path_by_id(self.stacks, resource_id)
        self.assertEqual(expected_full_path, full_path)


class TestGetStack(TestCase):
    root_stack = Stack("", "Root", "template.yaml", None, {})
    child_stack = Stack("Root", "Child", "root_stack/template.yaml", None, {})
    child_child_stack = Stack("Root/Child", "ChildChild", "root_stack/child_stack/template.yaml", None, {})

    def test_get_parent_stack(self):
        stack = Stack.get_parent_stack(self.child_stack, [self.root_stack, self.child_stack, self.child_child_stack])
        self.assertEqual(stack, self.root_stack)

        stack = Stack.get_parent_stack(self.root_stack, [self.root_stack, self.child_stack, self.child_child_stack])
        self.assertIsNone(stack)

    def test_get_stack_by_full_path(self):
        stack = Stack.get_stack_by_full_path("Root/Child", [self.root_stack, self.child_stack, self.child_child_stack])
        self.assertEqual(stack, self.child_stack)

        stack = Stack.get_stack_by_full_path("Root", [self.root_stack, self.child_stack, self.child_child_stack])
        self.assertEqual(stack, self.root_stack)

        stack = Stack.get_stack_by_full_path("Child/Child", [self.root_stack, self.child_stack, self.child_child_stack])
        self.assertIsNone(stack)

    def test_get_child_stacks(self):
        stack_list = Stack.get_child_stacks(
            self.root_stack, [self.root_stack, self.child_stack, self.child_child_stack]
        )
        self.assertEqual(stack_list, [self.child_stack])

        stack_list = Stack.get_child_stacks(
            self.child_stack, [self.root_stack, self.child_stack, self.child_child_stack]
        )
        self.assertEqual(stack_list, [self.child_child_stack])

        stack_list = Stack.get_child_stacks(
            self.child_child_stack, [self.root_stack, self.child_stack, self.child_child_stack]
        )
        self.assertEqual(stack_list, [])
