from unittest import TestCase
from unittest.mock import Mock

from samcli.commands.build.build_context import BuildContext
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.local.lambdafn.exceptions import ResourceNotFound


class TestBuildMultipleResources(TestCase):
    def _context(self, identifiers: tuple) -> BuildContext:
        template = {
            "Resources": {
                "First": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "src",
                        "Runtime": "python3.12",
                        "Handler": "app.handler",
                        "Layers": [{"Ref": "Shared"}],
                    },
                },
                "Second": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "src",
                        "Runtime": "python3.12",
                        "Handler": "app.handler",
                        "Layers": [{"Ref": "Shared"}],
                    },
                },
                "Unselected": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"CodeUri": "missing", "Runtime": "python3.12", "Handler": "app.handler"},
                },
                "Shared": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {"ContentUri": "layer"},
                    "Metadata": {"BuildMethod": "makefile"},
                },
            }
        }
        stacks = [Stack("", "", "template.yaml", {}, template), Stack("", "Child", "child.yaml", {}, template)]
        context = BuildContext(identifiers, "template.yaml", None, "build", "cache", False, False, None)
        context._function_provider = SamFunctionProvider(stacks, False)
        context._layer_provider = SamLayerProvider(stacks, False)
        context._web_function_provider = Mock()
        context._web_function_provider.get.return_value = None
        context._web_function_provider.get_all.return_value = []
        return context

    def test_builds_selected_functions_and_deduplicates_shared_layers(self) -> None:
        context = self._context(("First", "Second", "Shared", "First"))
        result = context.resources_to_build
        self.assertEqual([function.full_path for function in result.functions], ["First", "Second"])
        self.assertEqual([layer.full_path for layer in result.layers], ["Shared"])
        self.assertTrue(context.is_building_specific_resource)

    def test_preserves_distinct_resources_with_the_same_id_in_nested_stacks(self) -> None:
        result = self._context(("First", "Child/First")).resources_to_build
        self.assertEqual([function.full_path for function in result.functions], ["First", "Child/First"])
        self.assertEqual([layer.full_path for layer in result.layers], ["Shared", "Child/Shared"])

    def test_selects_multiple_layers_without_building_functions(self) -> None:
        result = self._context(("Shared", "Child/Shared", "Shared")).resources_to_build
        self.assertEqual(result.functions, [])
        self.assertEqual([layer.full_path for layer in result.layers], ["Shared", "Child/Shared"])

    def test_rejects_an_unknown_identifier_even_when_another_is_valid(self) -> None:
        with self.assertRaisesRegex(ResourceNotFound, "Missing"):
            self._context(("First", "Missing")).resources_to_build

    def test_warns_and_builds_explicitly_selected_excluded_resources(self) -> None:
        context = self._context(("First", "Second"))
        context._exclude = ("Second",)
        with self.assertLogs("samcli.commands.build.build_context", level="WARNING"):
            context._check_exclude_warning()
        self.assertEqual([function.name for function in context.resources_to_build.functions], ["First", "Second"])

    def test_resolves_all_error_resources_to_full_paths(self) -> None:
        context = self._context(("First", "Child/First"))
        self.assertEqual(
            context._resolve_resource_full_paths(("First", "Child/First", "Missing", "First")),
            ["First", "Child/First", "Missing"],
        )
