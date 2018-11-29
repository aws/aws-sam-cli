from unittest import TestCase
from mock import patch
from parameterized import parameterized

from samcli.commands.local.lib.provider import Function, LayerVersion
from samcli.commands.local.lib.sam_function_provider import SamFunctionProvider
from samcli.commands.local.lib.exceptions import InvalidLayerReference


class TestSamFunctionProviderEndToEnd(TestCase):
    """
    Test all public methods with an input template
    """

    TEMPLATE = {
        "Resources": {

            "SamFunc1": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "SamFunc2": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": "s3://bucket/key",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "SamFunc3": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": {
                        "Bucket": "bucket",
                        "Key": "key"
                    },
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "LambdaFunc1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {
                        "S3Bucket": "bucket",
                        "S3Key": "key"
                    },
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "LambdaFuncWithLocalPath": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": "./some/path/to/code",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "OtherResource": {
                "Type": "AWS::Serverless::Api",
                "Properties": {
                    "StageName": "prod",
                    "DefinitionUri": "s3://bucket/key"
                }
            }
        }
    }

    EXPECTED_FUNCTIONS = ["SamFunc1", "SamFunc2", "SamFunc3", "LambdaFunc1"]

    def setUp(self):
        self.parameter_overrides = {}
        self.provider = SamFunctionProvider(self.TEMPLATE, parameter_overrides=self.parameter_overrides)

    @parameterized.expand([
        ("SamFunc1", Function(
            name="SamFunc1",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri="/usr/foo/bar",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("SamFunc2", Function(
            name="SamFunc2",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("SamFunc3", Function(
            name="SamFunc3",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("LambdaFunc1", Function(
            name="LambdaFunc1",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("LambdaFuncWithLocalPath", Function(
            name="LambdaFuncWithLocalPath",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri="./some/path/to/code",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        ))
    ])
    def test_get_must_return_each_function(self, name, expected_output):

        actual = self.provider.get(name)
        self.assertEquals(actual, expected_output)

    def test_get_all_must_return_all_functions(self):

        result = {f.name for f in self.provider.get_all()}
        expected = {"SamFunc1", "SamFunc2", "SamFunc3", "LambdaFunc1", "LambdaFuncWithLocalPath"}

        self.assertEquals(result, expected)


class TestSamFunctionProvider_init(TestCase):

    def setUp(self):
        self.parameter_overrides = {}

    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.commands.local.lib.sam_function_provider.SamBaseProvider")
    def test_must_extract_functions(self, SamBaseProviderMock, extract_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        SamBaseProviderMock.get_template.return_value = template
        provider = SamFunctionProvider(template, parameter_overrides=self.parameter_overrides)

        extract_mock.assert_called_with({"a": "b"})
        SamBaseProviderMock.get_template.assert_called_with(template, self.parameter_overrides)
        self.assertEquals(provider.functions, extract_result)

    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.commands.local.lib.sam_function_provider.SamBaseProvider")
    def test_must_default_to_empty_resources(self, SamBaseProviderMock, extract_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"a": "b"}  # Template does *not* have 'Resources' key
        SamBaseProviderMock.get_template.return_value = template
        provider = SamFunctionProvider(template, parameter_overrides=self.parameter_overrides)

        extract_mock.assert_called_with({})  # Empty Resources value must be passed
        self.assertEquals(provider.functions, extract_result)
        self.assertEquals(provider.resources, {})


class TestSamFunctionProvider_extract_functions(TestCase):

    @patch.object(SamFunctionProvider, "_convert_sam_function_resource")
    def test_must_work_for_sam_function(self, convert_mock):
        convertion_result = "some result"
        convert_mock.return_value = convertion_result

        resources = {
            "Func1": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"a": "b"}
            }
        }

        expected = {
            "Func1": "some result"
        }

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEquals(expected, result)
        convert_mock.assert_called_with('Func1', {"a": "b"}, [])

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

        expected = {
            "Func1": "some result"
        }

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEquals(expected, result)
        convert_mock.assert_called_with('Func1', {}, [])

    @patch.object(SamFunctionProvider, "_convert_lambda_function_resource")
    def test_must_work_for_lambda_function(self, convert_mock):
        convertion_result = "some result"
        convert_mock.return_value = convertion_result

        resources = {
            "Func1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"a": "b"}
            }
        }

        expected = {
            "Func1": "some result"
        }

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEquals(expected, result)
        convert_mock.assert_called_with('Func1', {"a": "b"}, [])

    def test_must_skip_unknown_resource(self):
        resources = {
            "Func1": {
                "Type": "AWS::SomeOther::Function",
                "Properties": {"a": "b"}
            }
        }

        expected = {}

        result = SamFunctionProvider._extract_functions(resources)
        self.assertEquals(expected, result)


class TestSamFunctionProvider_convert_sam_function_resource(TestCase):

    def test_must_convert(self):

        name = "myname"
        properties = {
            "CodeUri": "/usr/local",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "mytimeout",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"]
        }

        expected = Function(
            name="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="mytimeout",
            handler="myhandler",
            codeuri="/usr/local",
            environment="myenvironment",
            rolearn="myrole",
            layers=["Layer1", "Layer2"]
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, ["Layer1", "Layer2"])

        self.assertEquals(expected, result)

    def test_must_skip_non_existent_properties(self):

        name = "myname"
        properties = {
            "CodeUri": "/usr/local"
        }

        expected = Function(
            name="myname",
            runtime=None,
            memory=None,
            timeout=None,
            handler=None,
            codeuri="/usr/local",
            environment=None,
            rolearn=None,
            layers=[]
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])

        self.assertEquals(expected, result)

    def test_must_default_missing_code_uri(self):

        name = "myname"
        properties = {
            "Runtime": "myruntime"
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])
        self.assertEquals(result.codeuri, ".")  # Default value

    def test_must_handle_code_dict(self):

        name = "myname"
        properties = {
            "CodeUri": {
                # CodeUri is some dictionary
                "a": "b"
            }
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])
        self.assertEquals(result.codeuri, ".")  # Default value

    def test_must_handle_code_s3_uri(self):

        name = "myname"
        properties = {
            "CodeUri": "s3://bucket/key"
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties, [])
        self.assertEquals(result.codeuri, ".")  # Default value


class TestSamFunctionProvider_convert_lambda_function_resource(TestCase):

    def test_must_convert(self):

        name = "myname"
        properties = {
            "Code": {
                "Bucket": "bucket"
            },
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "mytimeout",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"]
        }

        expected = Function(
            name="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="mytimeout",
            handler="myhandler",
            codeuri=".",
            environment="myenvironment",
            rolearn="myrole",
            layers=["Layer1", "Layer2"]
        )

        result = SamFunctionProvider._convert_lambda_function_resource(name, properties, ["Layer1", "Layer2"])

        self.assertEquals(expected, result)

    def test_must_skip_non_existent_properties(self):

        name = "myname"
        properties = {
            "Code": {
                "Bucket": "bucket"
            }
        }

        expected = Function(
            name="myname",
            runtime=None,
            memory=None,
            timeout=None,
            handler=None,
            codeuri=".",
            environment=None,
            rolearn=None,
            layers=[]
        )

        result = SamFunctionProvider._convert_lambda_function_resource(name, properties, [])

        self.assertEquals(expected, result)


class TestSamFunctionProvider_parse_layer_info(TestCase):

    @parameterized.expand([
        ({
            "Function": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                }
            }
        }, {"Ref": "Function"}),
        ({}, {"Ref": "LayerDoesNotExist"})
    ])
    def test_raise_on_invalid_layer_resource(self, resources, layer_reference):
        with self.assertRaises(InvalidLayerReference):
            SamFunctionProvider._parse_layer_info([layer_reference], resources)

    def test_layers_created_from_template_resources(self):
        resources = {
            "Layer": {
                "Type": "AWS::Lambda::LayerVersion",
                "Properties": {
                    "Content": {
                        "Bucket": "bucket"
                    }
                }
            },
            "ServerlessLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "ContentUri": "/somepath"
                }
            }
        }

        list_of_layers = [{"Ref": "Layer"},
                          {"Ref": "ServerlessLayer"},
                          "arn:aws:lambda:region:account-id:layer:layer-name:1",
                          {"NonRef": "Something"}]
        actual = SamFunctionProvider._parse_layer_info(list_of_layers, resources)

        for (actual_layer, expected_layer) in zip(actual, [LayerVersion("Layer", "."),
                                                           LayerVersion("ServerlessLayer", "/somepath"),
                                                           LayerVersion(
                                                               "arn:aws:lambda:region:account-id:layer:layer-name:1",
                                                               None)]):
            self.assertEquals(actual_layer, expected_layer)

    def test_return_empty_list_on_no_layers(self):
        resources = {
            "Function": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                }
            }
        }

        actual = SamFunctionProvider._parse_layer_info([], resources)

        self.assertEquals(actual, [])


class TestSamFunctionProvider_get(TestCase):

    def test_raise_on_invalid_name(self):
        provider = SamFunctionProvider({})

        with self.assertRaises(ValueError):
            provider.get(None)

    def test_must_return_function_value(self):
        provider = SamFunctionProvider({})
        provider.functions = {"func1": "value"}  # Cheat a bit here by setting the value of this property directly

        self.assertEquals("value", provider.get("func1"))

    def test_return_none_if_function_not_found(self):
        provider = SamFunctionProvider({})

        self.assertIsNone(provider.get("somefunc"), "Must return None when Function is not found")


class TestSamFunctionProvider_get_all(TestCase):

    def test_must_work_with_no_functions(self):
        provider = SamFunctionProvider({})

        result = [f for f in provider.get_all()]
        self.assertEquals(result, [])
