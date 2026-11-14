import posixpath
from unittest import TestCase
from unittest.mock import MagicMock, patch

from samcli.lib.providers.exceptions import MissingFunctionNameException

from parameterized import parameterized

from samcli.lib.providers.provider import (
    Function,
    FunctionBuildInfo,
    Stack,
    WebFunction,
    get_build_entry_point,
)
from samcli.lib.providers.sam_web_function_provider import (
    DEFAULT_ENTRY_POINT,
    SamWebFunctionProvider,
    stacks_have_web_functions,
)
from samcli.lib.utils.architecture import ARM64
from samcli.lib.utils.packagetype import ZIP

OTHER_RESOURCES = {"Bucket": {"Type": "AWS::S3::Bucket"}}


def _stack(resources, stack_path=""):
    return Stack("", stack_path, "template.yaml", {}, {"Resources": resources})


def _web_function(properties, metadata=None):
    resource = {"Type": "AWS::Serverless::WebFunction", "Properties": properties}
    if metadata is not None:
        resource["Metadata"] = metadata
    return resource


class TestSamWebFunctionProvider(TestCase):
    def test_extracts_buildable_web_functions(self):
        stack = _stack({"WebFn": _web_function({"Runtime": "nodejs24.x", "CodeUri": "./web"})})
        web_function = SamWebFunctionProvider([stack]).get("WebFn")
        self.assertIsInstance(web_function, WebFunction)
        self.assertEqual(web_function.runtime, "nodejs24.x")
        self.assertEqual(web_function.entry_point, DEFAULT_ENTRY_POINT)
        self.assertEqual(web_function.function_build_info, FunctionBuildInfo.BuildableZip)
        self.assertTrue(web_function.codeuri.endswith("web"))
        self.assertEqual(web_function.packagetype, ZIP)
        self.assertEqual(web_function.architecture, ARM64)

    def test_uses_entry_point_and_metadata(self):
        stack = _stack(
            {
                "WebFn": _web_function(
                    {"Runtime": "nodejs24.x", "CodeUri": "./web", "EntryPoint": "server.js", "FunctionName": "my-fn"},
                    {"BuildMethod": "esbuild", "SamResourceId": "CustomId"},
                )
            }
        )
        web_function = SamWebFunctionProvider([stack]).get("CustomId")
        self.assertEqual(web_function.entry_point, "server.js")
        self.assertEqual(web_function.metadata["BuildMethod"], "esbuild")
        self.assertEqual(web_function.functionname, "my-fn")
        self.assertEqual(web_function.full_path, "CustomId")

    @parameterized.expand([("s3://bucket/key.zip",), ({"Bucket": "bucket", "Key": "key.zip"},)])
    def test_web_functions_with_s3_code_are_not_built(self, code_uri):
        stack = _stack({"WebFn": _web_function({"Runtime": "nodejs24.x", "CodeUri": code_uri})})
        provider = SamWebFunctionProvider([stack], ignore_code_extraction_warnings=True)
        self.assertEqual(list(provider.get_all()), [])

    def test_ignores_other_resource_types(self):
        stack = _stack(
            {"Fn": {"Type": "AWS::Serverless::Function", "Properties": {"Runtime": "python3.13", "Handler": "a.b"}}}
        )
        self.assertEqual(list(SamWebFunctionProvider([stack]).get_all()), [])

    def test_finds_web_functions_in_nested_stacks(self):
        child = _stack({"WebFn": _web_function({"Runtime": "nodejs24.x", "CodeUri": "./web"})}, stack_path="Child")
        provider = SamWebFunctionProvider([_stack(OTHER_RESOURCES), child])
        full_path = posixpath.join("Child", "WebFn")
        self.assertEqual(provider.get(full_path).full_path, full_path)
        self.assertEqual(provider.get("WebFn").full_path, full_path)
        self.assertIsNone(provider.get("Missing"))

    def test_update_reloads_web_functions(self):
        provider = SamWebFunctionProvider([_stack(OTHER_RESOURCES)])
        provider.update([_stack({"WebFn": _web_function({"Runtime": "nodejs24.x", "CodeUri": "./web"})})])
        self.assertIsNotNone(provider.get("WebFn"))


class TestGetBuildEntryPoint(TestCase):
    def test_web_function_entry_point_and_function_handler(self):
        web_function = WebFunction(
            function_id="WebFn",
            name="WebFn",
            functionname="WebFn",
            runtime="nodejs24.x",
            codeuri="web",
            entry_point="server.js",
            metadata=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )
        self.assertEqual(get_build_entry_point(web_function), "server.js")

        function = Function(
            stack_path="",
            function_id="Fn",
            name="Fn",
            functionname="Fn",
            runtime="nodejs24.x",
            memory=None,
            timeout=None,
            handler="app.handler",
            imageuri=None,
            packagetype=ZIP,
            imageconfig=None,
            codeuri="fn",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            codesign_config_arn=None,
            architectures=None,
            function_url_config=None,
            function_build_info=FunctionBuildInfo.BuildableZip,
        )
        self.assertEqual(get_build_entry_point(function), "app.handler")


class TestSamWebFunctionProviderEdges(TestCase):
    def test_stacks_property_and_missing_name(self):
        stacks = [_stack(OTHER_RESOURCES)]
        provider = SamWebFunctionProvider(stacks)
        self.assertIs(provider.stacks, stacks)
        with self.assertRaises(MissingFunctionNameException):
            provider.get("")

    @patch("samcli.lib.providers.sam_web_function_provider.SamBaseProvider._warn_code_extraction")
    def test_warns_about_s3_code(self, warn_mock):
        stack = _stack({"WebFn": _web_function({"Runtime": "nodejs24.x", "CodeUri": "s3://bucket/key.zip"})})
        SamWebFunctionProvider([stack])
        warn_mock.assert_called_once_with("AWS::Serverless::WebFunction", "WebFn", "CodeUri")

    def test_raw_code_uri_is_kept(self):
        stack = _stack({"WebFn": _web_function({"Runtime": "nodejs24.x", "CodeUri": "web"})})
        self.assertEqual(SamWebFunctionProvider([stack], use_raw_codeuri=True).get("WebFn").codeuri, "web")


class TestWebFunctionProperties(TestCase):
    def _web_function(self, metadata=None, stack_path=""):
        return WebFunction(
            function_id="WebFn",
            name="WebFn",
            functionname="WebFn",
            runtime="nodejs24.x",
            codeuri="web",
            entry_point="index.js",
            metadata=metadata,
            function_build_info=FunctionBuildInfo.BuildableZip,
            stack_path=stack_path,
        )

    def test_skip_build(self):
        self.assertTrue(self._web_function({"SkipBuild": True}).skip_build)
        self.assertFalse(self._web_function().skip_build)

    def test_build_dir_includes_the_stack_path(self):
        import os

        self.assertEqual(
            self._web_function(stack_path="Child").get_build_dir("build"), os.path.join("build", "Child", "WebFn")
        )

    def test_build_architecture(self):
        from samcli.lib.build.utils import _get_function_architecture

        self.assertEqual(_get_function_architecture(self._web_function()), ARM64)


class TestStacksHaveWebFunctions(TestCase):
    def test_finds_web_functions_in_nested_stacks(self):
        root = _stack({"App": {"Type": "AWS::Serverless::Application", "Properties": {"Location": "child.yaml"}}})
        child = _stack(
            {"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "web/"}}}, stack_path="App"
        )
        self.assertFalse(stacks_have_web_functions([root]))
        self.assertTrue(stacks_have_web_functions([root, child], local_code_only=True))

    @parameterized.expand([("s3://bucket/key.zip",), ({"Bucket": "bucket", "Key": "key.zip"},)])
    def test_local_code_only_skips_s3_code(self, code_uri):
        stack = _stack({"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": code_uri}}})
        self.assertTrue(stacks_have_web_functions([stack]))
        self.assertFalse(stacks_have_web_functions([stack], local_code_only=True))


class TestTemplateFileHasLocalWebFunctions(TestCase):
    @patch("samcli.lib.providers.sam_stack_provider.SamLocalStackProvider.get_stacks")
    def test_detects_local_web_functions_in_nested_stacks(self, get_stacks_mock):
        from samcli.lib.providers.sam_web_function_provider import template_file_has_local_web_functions

        root = MagicMock(resources={"App": {"Type": "AWS::Serverless::Application"}})
        child = MagicMock(resources={"Fn": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "web/"}}})
        get_stacks_mock.return_value = ([root, child], [])
        self.assertTrue(template_file_has_local_web_functions("template.yaml"))
        get_stacks_mock.return_value = ([root], [])
        self.assertFalse(template_file_has_local_web_functions("template.yaml"))
        get_stacks_mock.side_effect = Exception("unreadable")
        self.assertFalse(template_file_has_local_web_functions("template.yaml"))


class TestCheckNoWebFunctionsInForEach(TestCase):
    def _stack(self, original_resources, stack_path=""):
        return MagicMock(stack_path=stack_path, original_template_dict={"Resources": original_resources})

    def _web_function(self, code_uri="${Name}/"):
        return {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": code_uri}}

    def test_rejects_web_functions_with_local_code_in_foreach(self):
        from samcli.lib.providers.sam_web_function_provider import (
            WebFunctionInForEachError,
            check_no_web_functions_in_foreach,
        )

        stack = self._stack({"Fn::ForEach::Sites": ["Name", ["a", "b"], {"WebFn${Name}": self._web_function()}]})
        with self.assertRaises(WebFunctionInForEachError) as ctx:
            check_no_web_functions_in_foreach([stack])
        self.assertIn("WebFn${Name}", ctx.exception.message)

    def test_rejects_nested_foreach_and_includes_the_stack_path(self):
        from samcli.lib.providers.sam_web_function_provider import (
            WebFunctionInForEachError,
            check_no_web_functions_in_foreach,
        )

        inner = {"Fn::ForEach::Inner": ["Env", ["dev"], {"WebFn${Name}${Env}": self._web_function()}]}
        stack = self._stack({"Fn::ForEach::Outer": ["Name", ["a"], inner]}, stack_path="Child")
        with self.assertRaises(WebFunctionInForEachError) as ctx:
            check_no_web_functions_in_foreach([stack])
        self.assertIn("Child/WebFn${Name}${Env}", ctx.exception.message)

    @parameterized.expand(
        [
            ("web function outside ForEach", {"WebFn": {"Type": "AWS::Serverless::WebFunction", "Properties": {}}}),
            (
                "Lambda function in ForEach",
                {"Fn::ForEach::F": ["N", ["a"], {"Fn${N}": {"Type": "AWS::Serverless::Function"}}]},
            ),
            (
                "Fn::Sub S3 code in ForEach",
                {
                    "Fn::ForEach::F": [
                        "N",
                        ["a"],
                        {
                            "WebFn${N}": {
                                "Type": "AWS::Serverless::WebFunction",
                                "Properties": {"CodeUri": {"Fn::Sub": "s3://bucket/${N}.zip"}},
                            }
                        },
                    ]
                },
            ),
            (
                "S3 code in ForEach",
                {
                    "Fn::ForEach::F": [
                        "N",
                        ["a"],
                        {"WebFn${N}": {"Type": "AWS::Serverless::WebFunction", "Properties": {"CodeUri": "s3://b/k"}}},
                    ]
                },
            ),
        ]
    )
    def test_allows_other_templates(self, _, resources):
        from samcli.lib.providers.sam_web_function_provider import check_no_web_functions_in_foreach

        check_no_web_functions_in_foreach([self._stack(resources)])

    def test_ignores_stacks_without_an_original_template(self):
        from samcli.lib.providers.sam_web_function_provider import check_no_web_functions_in_foreach

        check_no_web_functions_in_foreach([MagicMock(stack_path="", original_template_dict=None)])
