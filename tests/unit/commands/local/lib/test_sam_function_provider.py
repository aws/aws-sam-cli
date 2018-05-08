from unittest import TestCase
from mock import patch
from parameterized import parameterized

from samcli.commands.local.lib.provider import Function
from samcli.commands.local.lib.sam_function_provider import SamFunctionProvider


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
        self.provider = SamFunctionProvider(self.TEMPLATE)

    @parameterized.expand([
        ("SamFunc1", Function(
            name="SamFunc1",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri="/usr/foo/bar",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None
        )),
        ("SamFunc2", Function(
            name="SamFunc2",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None
        )),
        ("SamFunc3", Function(
            name="SamFunc3",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None
        )),
        ("LambdaFunc1", Function(
            name="LambdaFunc1",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None
        ))
    ])
    def test_get_must_return_each_function(self, name, expected_output):

        actual = self.provider.get(name)
        self.assertEquals(actual, expected_output)

    def test_get_all_must_return_all_functions(self):

        result = {f.name for f in self.provider.get_all()}
        expected = {"SamFunc1", "SamFunc2", "SamFunc3", "LambdaFunc1"}

        self.assertEquals(result, expected)


class TestSamFunctionProvider_init(TestCase):

    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.commands.local.lib.sam_function_provider.SamBaseProvider")
    def test_must_extract_functions(self, SamBaseProviderMock, extract_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        SamBaseProviderMock.get_template.return_value = template
        provider = SamFunctionProvider(template)

        extract_mock.assert_called_with({"a": "b"})
        SamBaseProviderMock.get_template.assert_called_with(template)
        self.assertEquals(provider.functions, extract_result)

    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.commands.local.lib.sam_function_provider.SamBaseProvider")
    def test_must_default_to_empty_resources(self, SamBaseProviderMock, extract_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"a": "b"}  # Template does *not* have 'Resources' key
        SamBaseProviderMock.get_template.return_value = template
        provider = SamFunctionProvider(template)

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
        convert_mock.assert_called_with('Func1', {"a": "b"})

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
        convert_mock.assert_called_with('Func1', {})

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
        convert_mock.assert_called_with('Func1', {"a": "b"})

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
            "Role": "myrole"
        }

        expected = Function(
            name="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="mytimeout",
            handler="myhandler",
            codeuri="/usr/local",
            environment="myenvironment",
            rolearn="myrole"
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties)

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
            rolearn=None
        )

        result = SamFunctionProvider._convert_sam_function_resource(name, properties)

        self.assertEquals(expected, result)

    def test_must_default_missing_code_uri(self):

        name = "myname"
        properties = {
            "Runtime": "myruntime"
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties)
        self.assertEquals(result.codeuri, ".")  # Default value

    def test_must_handle_code_dict(self):

        name = "myname"
        properties = {
            "CodeUri": {
                # CodeUri is some dictionary
                "a": "b"
            }
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties)
        self.assertEquals(result.codeuri, ".")  # Default value

    def test_must_handle_code_s3_uri(self):

        name = "myname"
        properties = {
            "CodeUri": "s3://bucket/key"
        }

        result = SamFunctionProvider._convert_sam_function_resource(name, properties)
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
            "Role": "myrole"
        }

        expected = Function(
            name="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="mytimeout",
            handler="myhandler",
            codeuri=".",
            environment="myenvironment",
            rolearn="myrole"
        )

        result = SamFunctionProvider._convert_lambda_function_resource(name, properties)

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
            rolearn=None
        )

        result = SamFunctionProvider._convert_lambda_function_resource(name, properties)

        self.assertEquals(expected, result)


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
