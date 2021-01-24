from unittest import TestCase
from unittest.mock import patch
from parameterized import parameterized

from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn
from samcli.lib.providers.provider import Function, LayerVersion
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.exceptions import InvalidLayerReference
from samcli.lib.utils.packagetype import IMAGE, ZIP


class TestSamFunctionProviderEndToEnd(TestCase):
    """
    Test all public methods with an input template
    """

    TEMPLATE = {
        "Resources": {
            "SamFunctions": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFunc1",
                    "CodeUri": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFunc2": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": "s3://bucket/key",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFunc3": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": {"Bucket": "bucket", "Key": "key"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFunc4": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo", "PackageType": IMAGE},
            },
            "SamFuncWithFunctionNameOverride": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFuncWithFunctionNameOverride-x",
                    "CodeUri": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "LambdaFunc1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"S3Bucket": "bucket", "S3Key": "key"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "LambdaFunc2": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo"},
                    "PackageType": IMAGE,
                },
            },
            "LambdaFuncWithLocalPath": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": "./some/path/to/code", "Runtime": "nodejs4.3", "Handler": "index.handler"},
            },
            "LambdaFuncWithFunctionNameOverride": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "FunctionName": "LambdaFuncWithFunctionNameOverride-x",
                    "Code": "./some/path/to/code",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "LambdaFuncWithCodeSignConfig": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "FunctionName": "LambdaFuncWithCodeSignConfig",
                    "Code": "./some/path/to/code",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                    "CodeSigningConfigArn": "codeSignConfigArn",
                },
            },
            "OtherResource": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"StageName": "prod", "DefinitionUri": "s3://bucket/key"},
            },
        }
    }

    def setUp(self):
        self.parameter_overrides = {}
        self.provider = SamFunctionProvider(self.TEMPLATE, parameter_overrides=self.parameter_overrides)

    @parameterized.expand(
        [
            (
                "SamFunc1",
                Function(
                    name="SamFunctions",
                    functionname="SamFunc1",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                ),
            ),
            (
                "SamFunctions",
                Function(
                    name="SamFunctions",
                    functionname="SamFunc1",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                ),
            ),
            (
                "SamFunc2",
                Function(
                    name="SamFunc2",
                    functionname="SamFunc2",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                ),
            ),
            (
                "SamFunc3",
                Function(
                    name="SamFunc3",
                    functionname="SamFunc3",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    metadata=None,
                    codesign_config_arn=None,
                ),
            ),
            (
                "SamFunc4",
                Function(
                    name="SamFunc4",
                    functionname="SamFunc4",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    imageuri="123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo",
                    imageconfig=None,
                    packagetype=IMAGE,
                    metadata=None,
                    codesign_config_arn=None,
                ),
            ),
            (
                "SamFuncWithFunctionNameOverride-x",
                Function(
                    name="SamFuncWithFunctionNameOverride",
                    functionname="SamFuncWithFunctionNameOverride-x",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                ),
            ),
            (
                "LambdaFunc1",
                Function(
                    name="LambdaFunc1",
                    functionname="LambdaFunc1",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                ),
            ),
            (
                "LambdaFunc2",
                Function(
                    name="LambdaFunc2",
                    functionname="LambdaFunc2",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri="123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo",
                    imageconfig=None,
                    packagetype=IMAGE,
                    codesign_config_arn=None,
                ),
            ),
            (
                "LambdaFuncWithLocalPath",
                Function(
                    name="LambdaFuncWithLocalPath",
                    functionname="LambdaFuncWithLocalPath",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="./some/path/to/code",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    codesign_config_arn=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                ),
            ),
            (
                "LambdaFuncWithFunctionNameOverride-x",
                Function(
                    name="LambdaFuncWithFunctionNameOverride",
                    functionname="LambdaFuncWithFunctionNameOverride-x",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="./some/path/to/code",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                ),
            ),
            (
                "LambdaFuncWithCodeSignConfig",
                Function(
                    name="LambdaFuncWithCodeSignConfig",
                    functionname="LambdaFuncWithCodeSignConfig",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="./some/path/to/code",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn="codeSignConfigArn",
                ),
            ),
        ]
    )
    def test_get_must_return_each_function(self, name, expected_output):

        actual = self.provider.get(name)
        self.assertEqual(actual, expected_output)

    def test_get_all_must_return_all_functions(self):

        result = {f.name for f in self.provider.get_all()}
        expected = {
            "SamFunctions",
            "SamFunc2",
            "SamFunc3",
            "SamFunc4",
            "SamFuncWithFunctionNameOverride",
            "LambdaFunc1",
            "LambdaFunc2",
            "LambdaFuncWithLocalPath",
            "LambdaFuncWithFunctionNameOverride",
            "LambdaFuncWithCodeSignConfig",
        }

        self.assertEqual(result, expected)


class TestSamFunctionProvider_init(TestCase):
    def setUp(self):
        self.parameter_overrides = {}

    @patch.object(SamFunctionProvider, "get_template")
    @patch.object(SamFunctionProvider, "_extract_functions")
    def test_must_extract_functions(self, extract_mock, get_template_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        provider = SamFunctionProvider(template, parameter_overrides=self.parameter_overrides)

        extract_mock.assert_called_with({"a": "b"}, False)
        get_template_mock.assert_called_with(template, self.parameter_overrides)
        self.assertEqual(provider.functions, extract_result)

    @patch.object(SamFunctionProvider, "get_template")
    @patch.object(SamFunctionProvider, "_extract_functions")
    def test_must_default_to_empty_resources(self, extract_mock, get_template_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"a": "b"}  # Template does *not* have 'Resources' key
        get_template_mock.return_value = template
        provider = SamFunctionProvider(template, parameter_overrides=self.parameter_overrides)

        extract_mock.assert_called_with({}, False)  # Empty Resources value must be passed
        self.assertEqual(provider.functions, extract_result)
        self.assertEqual(provider.resources, {})


class TestSamFunctionProvider_extract_functions(TestCase):
    @patch.object(SamFunctionProvider, "_convert_sam_function_resource")
    def test_must_work_for_sam_function(self, convert_mock):
        convertion_result = "some result"
        convert_mock.return_value = convertion_result

        resources = {"Func1": {"Type": "AWS::Serverless::Function", "Properties": {"a": "b"}}}

        expected = {"Func1": "some result"}

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEqual(expected, result)
        convert_mock.assert_called_with("Func1", {"a": "b"}, [], ignore_code_extraction_warnings=False)

    @patch.object(SamFunctionProvider, "_convert_sam_function_resource")
    def test_must_work_with_no_properties(self, convert_mock):
        convertion_result = "some result"
        convert_mock.return_value = convertion_result

        resources = {
            "Func1": {
                "Type": "AWS::Serverless::Function"
                # No Properties
            }
        }

        expected = {"Func1": "some result"}

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEqual(expected, result)
        convert_mock.assert_called_with("Func1", {}, [], ignore_code_extraction_warnings=False)

    @patch.object(SamFunctionProvider, "_convert_lambda_function_resource")
    def test_must_work_for_lambda_function(self, convert_mock):
        convertion_result = "some result"
        convert_mock.return_value = convertion_result

        resources = {"Func1": {"Type": "AWS::Lambda::Function", "Properties": {"a": "b"}}}

        expected = {"Func1": "some result"}

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEqual(expected, result)
        convert_mock.assert_called_with("Func1", {"a": "b"}, [])

    def test_must_skip_unknown_resource(self):
        resources = {"Func1": {"Type": "AWS::SomeOther::Function", "Properties": {"a": "b"}}}

        expected = {}

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEqual(expected, result)


class TestSamFunctionProvider_convert_sam_function_resource(TestCase):
    def test_must_convert_zip(self):

        name = "myname"
        properties = {
            "CodeUri": "/usr/local",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
        }

        expected = Function(
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri="/usr/local",
            environment="myenvironment",
            rolearn="myrole",
            layers=["Layer1", "Layer2"],
            events=None,
            metadata=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, ["Layer1", "Layer2"])

        self.assertEqual(expected, result)

    def test_must_convert_image(self):

        name = "myname"
        properties = {
            "ImageUri": "helloworld:v1",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "ImageConfig": {"WorkingDirectory": "/var/task", "Command": "/bin/bash", "EntryPoint": "echo Hello!"},
            "PackageType": IMAGE,
        }

        expected = Function(
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri=".",
            environment="myenvironment",
            rolearn="myrole",
            layers=[],
            events=None,
            metadata=None,
            imageuri="helloworld:v1",
            imageconfig={"WorkingDirectory": "/var/task", "Command": "/bin/bash", "EntryPoint": "echo Hello!"},
            packagetype=IMAGE,
            codesign_config_arn=None,
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])

        self.assertEqual(expected, result)

    def test_must_skip_non_existent_properties(self):

        name = "myname"
        properties = {"CodeUri": "/usr/local"}

        expected = Function(
            name="myname",
            functionname="myname",
            runtime=None,
            memory=None,
            timeout=None,
            handler=None,
            codeuri="/usr/local",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])

        self.assertEqual(expected, result)

    def test_must_default_missing_code_uri(self):

        name = "myname"
        properties = {"Runtime": "myruntime"}

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])
        self.assertEqual(result.codeuri, ".")  # Default value

    def test_must_handle_code_dict(self):

        name = "myname"
        properties = {
            "CodeUri": {
                # CodeUri is some dictionary
                "a": "b"
            }
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])
        self.assertEqual(result.codeuri, ".")  # Default value

    def test_must_handle_code_s3_uri(self):

        name = "myname"
        properties = {"CodeUri": "s3://bucket/key"}

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])
        self.assertEqual(result.codeuri, ".")  # Default value


class TestSamFunctionProvider_convert_lambda_function_resource(TestCase):
    def test_must_convert(self):

        name = "myname"
        properties = {
            "Code": {"Bucket": "bucket"},
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
        }

        expected = Function(
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri=".",
            environment="myenvironment",
            rolearn="myrole",
            layers=["Layer1", "Layer2"],
            events=None,
            metadata=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
        )

        result = SamFunctionProvider._convert_lambda_function_resource(name, properties, ["Layer1", "Layer2"])

        self.assertEqual(expected, result)

    def test_must_skip_non_existent_properties(self):

        name = "myname"
        properties = {"Code": {"Bucket": "bucket"}}

        expected = Function(
            name="myname",
            functionname="myname",
            runtime=None,
            memory=None,
            timeout=None,
            handler=None,
            codeuri=".",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
        )

        result = SamFunctionProvider._convert_lambda_function_resource(name, properties, [])

        self.assertEqual(expected, result)


class TestSamFunctionProvider_parse_layer_info(TestCase):
    @parameterized.expand(
        [
            ({"Function": {"Type": "AWS::Serverless::Function", "Properties": {}}}, {"Ref": "Function"}),
            ({}, {"Ref": "LayerDoesNotExist"}),
        ]
    )
    def test_raise_on_invalid_layer_resource(self, resources, layer_reference):
        with self.assertRaises(InvalidLayerReference):
            SamFunctionProvider._parse_layer_info([layer_reference], resources)

    @parameterized.expand(
        [
            (
                {"Function": {"Type": "AWS::Serverless::Function", "Properties": {}}},
                "arn:aws:lambda:::awslayer:AmazonLinux1703",
            )
        ]
    )
    def test_raise_on_AmazonLinux1703_layer_provided(self, resources, layer_reference):
        with self.assertRaises(InvalidLayerVersionArn):
            SamFunctionProvider._parse_layer_info([layer_reference], resources)

    def test_must_ignore_opt_in_AmazonLinux1803_layer(self):
        resources = {}

        list_of_layers = [
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            "arn:aws:lambda:::awslayer:AmazonLinux1803",
        ]
        actual = SamFunctionProvider._parse_layer_info(list_of_layers, resources)

        for (actual_layer, expected_layer) in zip(
            actual, [LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None)]
        ):
            self.assertEqual(actual_layer, expected_layer)

    def test_layers_created_from_template_resources(self):
        resources = {
            "Layer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": {"Bucket": "bucket"}}},
            "ServerlessLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "/somepath"}},
        }

        list_of_layers = [
            {"Ref": "Layer"},
            {"Ref": "ServerlessLayer"},
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            {"NonRef": "Something"},
        ]
        actual = SamFunctionProvider._parse_layer_info(list_of_layers, resources)

        for (actual_layer, expected_layer) in zip(
            actual,
            [
                LayerVersion("Layer", "."),
                LayerVersion("ServerlessLayer", "/somepath"),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None),
            ],
        ):
            self.assertEqual(actual_layer, expected_layer)

    def test_return_empty_list_on_no_layers(self):
        resources = {"Function": {"Type": "AWS::Serverless::Function", "Properties": {}}}

        actual = SamFunctionProvider._parse_layer_info([], resources)

        self.assertEqual(actual, [])


class TestSamFunctionProvider_get(TestCase):
    def test_raise_on_invalid_name(self):
        provider = SamFunctionProvider({})

        with self.assertRaises(ValueError):
            provider.get(None)

    def test_must_return_function_value(self):
        provider = SamFunctionProvider({})
        # Cheat a bit here by setting the value of this property directly
        function = Function(
            name="not-value",
            functionname="value",
            runtime=None,
            handler=None,
            codeuri=None,
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            imageuri=None,
            imageconfig=None,
            packagetype=None,
            codesign_config_arn=None,
        )
        provider.functions = {"func1": function}

        self.assertEqual(function, provider.get("value"))

    def test_return_none_if_function_not_found(self):
        provider = SamFunctionProvider({})

        self.assertIsNone(provider.get("somefunc"), "Must return None when Function is not found")


class TestSamFunctionProvider_get_all(TestCase):
    def test_must_work_with_no_functions(self):
        provider = SamFunctionProvider({})

        result = [f for f in provider.get_all()]
        self.assertEqual(result, [])
