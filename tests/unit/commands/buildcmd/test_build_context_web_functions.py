from unittest import TestCase
from unittest.mock import MagicMock, patch

from samcli.commands.build.build_context import BuildContext
from samcli.local.lambdafn.exceptions import ResourceNotFound
from samcli.lib.providers.provider import FunctionBuildInfo, WebFunction


def _web_function(name, build_info=FunctionBuildInfo.BuildableZip):
    return WebFunction(
        function_id=name,
        name=name,
        functionname=name,
        runtime="nodejs24.x",
        codeuri="web",
        entry_point="index.js",
        metadata=None,
        function_build_info=build_info,
    )


class TestBuildContextWebFunctions(TestCase):
    def _context(self, web_functions, excluded=None):
        context = BuildContext(
            resource_identifier=None,
            template_file="template.yaml",
            base_dir=None,
            build_dir="build",
            cache_dir="cache",
            cached=False,
            parallel=False,
            mode=None,
            excluded_resources=excluded,
        )
        context._function_provider = MagicMock()
        context._function_provider.get_all.return_value = []
        context._function_provider.get.return_value = None
        context._layer_provider = MagicMock()
        context._layer_provider.get_all.return_value = []
        context._layer_provider.get.return_value = None
        context._web_function_provider = MagicMock()
        context._web_function_provider.get_all.return_value = web_functions
        context._web_function_provider.get.side_effect = lambda name: next(
            (f for f in web_functions if f.name == name), None
        )
        return context

    def test_collects_buildable_web_functions(self):
        buildable = _web_function("WebFn")
        skipped = _web_function("SkippedFn", FunctionBuildInfo.SkipBuild)
        excluded = _web_function("ExcludedFn")
        result = self._context([buildable, skipped, excluded], excluded=("ExcludedFn",)).collect_all_build_resources()
        self.assertEqual(result.functions, [buildable])

    def test_collects_a_single_web_function(self):
        web_function = _web_function("WebFn")
        result = self._context([web_function]).collect_build_resources("WebFn")
        self.assertEqual(result.functions, [web_function])
        self.assertEqual(result.layers, [])

    def test_unknown_identifier_lists_web_functions(self):
        context = self._context([_web_function("WebFn")])
        with self.assertLogs("samcli.commands.build.build_context", level="INFO") as logs:
            with self.assertRaises(ResourceNotFound):
                context.collect_build_resources("Missing")
        self.assertIn("WebFn", "".join(logs.output))

    def test_resolves_web_function_full_path(self):
        context = self._context([_web_function("WebFn")])
        self.assertEqual(context._resolve_resource_full_paths("WebFn"), ["WebFn"])


class TestBuildContextWebFunctionsInForEach(TestCase):
    @patch("samcli.commands.build.build_context.SamLocalStackProvider.get_stacks")
    def test_enter_rejects_web_functions_in_foreach(self, get_stacks_mock):
        from samcli.lib.package.web_function_code_access import WebFunctionInForEachError
        from samcli.lib.providers.provider import Stack

        original = {
            "Resources": {
                "Fn::ForEach::Sites": [
                    "Name",
                    ["a"],
                    {"WebFn${Name}": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "${Name}/"}}},
                ]
            }
        }
        expanded = {"Resources": {"WebFna": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "a/"}}}}
        stack = Stack("", "", "template.yaml", {}, expanded, original_template_dict=original)
        get_stacks_mock.return_value = ([stack], [])
        context = BuildContext(
            resource_identifier=None,
            template_file="template.yaml",
            base_dir=None,
            build_dir="build",
            cache_dir="cache",
            cached=False,
            parallel=False,
            mode=None,
        )
        with self.assertRaises(WebFunctionInForEachError):
            context.__enter__()
