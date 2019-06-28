import json
import tempfile
from unittest import TestCase

from mock import patch
from six import assertCountEqual

from samcli.commands.local.lib.api_provider import ApiProvider
from samcli.commands.local.lib.provider import Api
from tests.unit.commands.local.lib.test_sam_api_provider import make_swagger


class TestApiProviderWithApiGatewayRestApi(TestCase):

    def setUp(self):
        self.binary_types = ["image/png", "image/jpg"]
        self.input_apis = [
            Api(path="/path1", method="GET", function_name="SamFunc1", cors=None),
            Api(path="/path1", method="POST", function_name="SamFunc1", cors=None),

            Api(path="/path2", method="PUT", function_name="SamFunc1", cors=None),
            Api(path="/path2", method="GET", function_name="SamFunc1", cors=None),

            Api(path="/path3", method="DELETE", function_name="SamFunc1", cors=None)
        ]

    def test_with_no_apis(self):
        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                    },

                }
            }
        }

        provider = ApiProvider(template)

        self.assertEquals(provider.apis, [])

    def test_with_inline_swagger_apis(self):
        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Body": make_swagger(self.input_apis)
                    }
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, self.input_apis, provider.apis)

    def test_with_swagger_as_local_file(self):
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            filename = fp.name

            swagger = make_swagger(self.input_apis)
            json.dump(swagger, fp)
            fp.flush()

            template = {
                "Resources": {

                    "Api1": {
                        "Type": "AWS::ApiGateway::RestApi",
                        "Properties": {
                            "BodyS3Location": filename
                        }
                    }
                }
            }

            provider = ApiProvider(template)
            assertCountEqual(self, self.input_apis, provider.apis)

    def test_body_with_swagger_as_local_file_expect_fail(self):
        with tempfile.NamedTemporaryFile(mode='w') as fp:
            filename = fp.name

            swagger = make_swagger(self.input_apis)
            json.dump(swagger, fp)
            fp.flush()

            template = {
                "Resources": {

                    "Api1": {
                        "Type": "AWS::ApiGateway::RestApi",
                        "Properties": {
                            "Body": filename
                        }
                    }
                }
            }
            self.assertRaises(Exception, ApiProvider, template)

    @patch("samcli.commands.local.lib.cfn_base_api_provider.SamSwaggerReader")
    def test_with_swagger_as_both_body_and_uri_called(self, SamSwaggerReaderMock):
        body = {"some": "body"}
        filename = "somefile.txt"

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "BodyS3Location": filename,
                        "Body": body
                    }
                }
            }
        }

        SamSwaggerReaderMock.return_value.read.return_value = make_swagger(self.input_apis)

        cwd = "foo"
        provider = ApiProvider(template, cwd=cwd)
        assertCountEqual(self, self.input_apis, provider.apis)
        SamSwaggerReaderMock.assert_called_with(definition_body=body, definition_uri=filename, working_dir=cwd)

    def test_swagger_with_any_method(self):
        apis = [
            Api(path="/path", method="any", function_name="SamFunc1", cors=None)
        ]

        expected_apis = [
            Api(path="/path", method="GET", function_name="SamFunc1", cors=None),
            Api(path="/path", method="POST", function_name="SamFunc1", cors=None),
            Api(path="/path", method="PUT", function_name="SamFunc1", cors=None),
            Api(path="/path", method="DELETE", function_name="SamFunc1", cors=None),
            Api(path="/path", method="HEAD", function_name="SamFunc1", cors=None),
            Api(path="/path", method="OPTIONS", function_name="SamFunc1", cors=None),
            Api(path="/path", method="PATCH", function_name="SamFunc1", cors=None)
        ]

        template = {
            "Resources": {
                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Body": make_swagger(apis)
                    }
                }
            }
        }

        provider = ApiProvider(template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_with_binary_media_types(self):
        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "Body": make_swagger(self.input_apis, binary_media_types=self.binary_types)
                    }
                }
            }
        }

        expected_binary_types = sorted(self.binary_types)
        expected_apis = [
            Api(path="/path1", method="GET", function_name="SamFunc1", cors=None,
                binary_media_types=expected_binary_types),
            Api(path="/path1", method="POST", function_name="SamFunc1", cors=None,
                binary_media_types=expected_binary_types),

            Api(path="/path2", method="PUT", function_name="SamFunc1", cors=None,
                binary_media_types=expected_binary_types),
            Api(path="/path2", method="GET", function_name="SamFunc1", cors=None,
                binary_media_types=expected_binary_types),

            Api(path="/path3", method="DELETE", function_name="SamFunc1", cors=None,
                binary_media_types=expected_binary_types)
        ]

        provider = ApiProvider(template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_with_binary_media_types_in_swagger_and_on_resource(self):
        input_apis = [
            Api(path="/path", method="OPTIONS", function_name="SamFunc1"),
        ]
        extra_binary_types = ["text/html"]

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::ApiGateway::RestApi",
                    "Properties": {
                        "BinaryMediaTypes": extra_binary_types,
                        "Body": make_swagger(input_apis, binary_media_types=self.binary_types)
                    }
                }
            }
        }

        expected_binary_types = sorted(self.binary_types + extra_binary_types)
        expected_apis = [
            Api(path="/path", method="OPTIONS", function_name="SamFunc1", binary_media_types=expected_binary_types),
        ]

        provider = ApiProvider(template)
        assertCountEqual(self, expected_apis, provider.apis)
