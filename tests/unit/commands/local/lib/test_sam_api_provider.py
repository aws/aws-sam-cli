import tempfile
import json

from unittest import TestCase
from mock import patch
from nose_parameterized import parameterized

from six import assertCountEqual

from samcli.commands.local.lib.sam_api_provider import SamApiProvider
from samcli.commands.local.lib.provider import Api
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

import logging
logging.basicConfig(level=logging.INFO)


class TestSamApiProvider_init(TestCase):

    @patch.object(SamApiProvider, "_extract_apis")
    @patch("samcli.commands.local.lib.sam_api_provider.SamBaseProvider")
    def test_provider_with_valid_template(self, SamBaseProviderMock, extract_api_mock):
        extract_api_mock.return_value = {"set", "of", "values"}

        template = {"Resources": {"a": "b"}}
        SamBaseProviderMock.get_template.return_value = template

        provider = SamApiProvider(template)

        self.assertEquals(len(provider.apis), 3)
        self.assertEquals(provider.apis, set(["set", "of", "values"]))
        self.assertEquals(provider.template_dict, {"Resources": {"a": "b"}})
        self.assertEquals(provider.resources, {"a": "b"})


class TestSamApiProviderWithImplicitApis(TestCase):

    def test_provider_with_no_resource_properties(self):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Lambda::Function"
                }
            }
        }

        provider = SamApiProvider(template)

        self.assertEquals(len(provider.apis), 0)
        self.assertEquals(provider.apis, [])

    @parameterized.expand([("GET"), ("get")])
    def test_provider_has_correct_api(self, method):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": method
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        self.assertEquals(len(provider.apis), 1)
        self.assertEquals(list(provider.apis)[0], Api(path="/path", method="GET", function_name="SamFunc1", cors=None))

    def test_provider_creates_api_for_all_events(self):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "GET"
                                }
                            },
                            "Event2": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "POST"
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        api_event1 = Api(path="/path", method="GET", function_name="SamFunc1", cors=None)
        api_event2 = Api(path="/path", method="POST", function_name="SamFunc1", cors=None)

        self.assertIn(api_event1, provider.apis)
        self.assertIn(api_event2, provider.apis)
        self.assertEquals(len(provider.apis), 2)

    def test_provider_has_correct_template(self):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "GET"
                                }
                            }
                        }
                    }
                },
                "SamFunc2": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "POST"
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        api1 = Api(path="/path", method="GET", function_name="SamFunc1", cors=None)
        api2 = Api(path="/path", method="POST", function_name="SamFunc2", cors=None)

        self.assertIn(api1, provider.apis)
        self.assertIn(api2, provider.apis)

    def test_provider_with_no_api_events(self):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "S3",
                                "Properties": {
                                    "Property1": "value"
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        self.assertEquals(provider.apis, [])

    def test_provider_with_no_serverless_function(self):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler"
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        self.assertEquals(provider.apis, [])

    def test_provider_get_all(self):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "GET"
                                }
                            }
                        }
                    }
                },
                "SamFunc2": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "POST"
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        result = [f for f in provider.get_all()]

        api1 = Api(path="/path", method="GET", function_name="SamFunc1")
        api2 = Api(path="/path", method="POST", function_name="SamFunc2")

        self.assertIn(api1, result)
        self.assertIn(api2, result)

    def test_provider_get_all_with_no_apis(self):
        template = {}

        provider = SamApiProvider(template)

        result = [f for f in provider.get_all()]

        self.assertEquals(result, [])

    @parameterized.expand([("ANY"), ("any")])
    def test_provider_with_any_method(self, method):
        template = {
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": method
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        api_get = Api(path="/path", method="GET", function_name="SamFunc1", cors=None)
        api_post = Api(path="/path", method="POST", function_name="SamFunc1", cors=None)
        api_put = Api(path="/path", method="PUT", function_name="SamFunc1", cors=None)
        api_delete = Api(path="/path", method="DELETE", function_name="SamFunc1", cors=None)
        api_patch = Api(path="/path", method="PATCH", function_name="SamFunc1", cors=None)
        api_head = Api(path="/path", method="HEAD", function_name="SamFunc1", cors=None)
        api_options = Api(path="/path", method="OPTIONS", function_name="SamFunc1", cors=None)

        self.assertEquals(len(provider.apis), 7)
        self.assertIn(api_get, provider.apis)
        self.assertIn(api_post, provider.apis)
        self.assertIn(api_put, provider.apis)
        self.assertIn(api_delete, provider.apis)
        self.assertIn(api_patch, provider.apis)
        self.assertIn(api_head, provider.apis)
        self.assertIn(api_options, provider.apis)

    def test_provider_must_support_binary_media_types(self):
        template = {
            "Globals": {
                "Api": {
                    "BinaryMediaTypes": [
                        "image~1gif",
                        "image~1png",
                        "image~1png",  # Duplicates must be ignored
                        {"Ref": "SomeParameter"}  # Refs are ignored as well
                    ]
                }
            },
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "get"
                                }
                            }
                        }
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        self.assertEquals(len(provider.apis), 1)
        self.assertEquals(list(provider.apis)[0], Api(path="/path", method="GET", function_name="SamFunc1",
                                                      binary_media_types=["image/gif", "image/png"], cors=None))

    def test_provider_must_support_binary_media_types_with_any_method(self):
        template = {
            "Globals": {
                "Api": {
                    "BinaryMediaTypes": [
                        "image~1gif",
                        "image~1png",
                        "text/html"
                    ]
                }
            },
            "Resources": {

                "SamFunc1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler",
                        "Events": {
                            "Event1": {
                                "Type": "Api",
                                "Properties": {
                                    "Path": "/path",
                                    "Method": "any"
                                }
                            }
                        }
                    }
                }
            }
        }

        binary = ["image/gif", "image/png", "text/html"]

        expected_apis = [
            Api(path="/path", method="GET", function_name="SamFunc1", binary_media_types=binary),
            Api(path="/path", method="POST", function_name="SamFunc1", binary_media_types=binary),
            Api(path="/path", method="PUT", function_name="SamFunc1", binary_media_types=binary),
            Api(path="/path", method="DELETE", function_name="SamFunc1", binary_media_types=binary),
            Api(path="/path", method="HEAD", function_name="SamFunc1", binary_media_types=binary),
            Api(path="/path", method="OPTIONS", function_name="SamFunc1", binary_media_types=binary),
            Api(path="/path", method="PATCH", function_name="SamFunc1", binary_media_types=binary)
        ]

        provider = SamApiProvider(template)

        assertCountEqual(self, provider.apis, expected_apis)

    def test_convert_event_api_with_invalid_event_properties(self):
        properties = {
            "Path": "/foo",
            "Method": "get",
            "RestApiId": {
                # This is not supported. Only Ref is supported
                "Fn::Sub": "foo"
            }
        }

        with self.assertRaises(InvalidSamDocumentException):
            SamApiProvider._convert_event_api("logicalId", properties)


class TestSamApiProviderWithExplicitApis(TestCase):

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
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod"
                    }
                }
            }
        }

        provider = SamApiProvider(template)

        self.assertEquals(len(provider.apis), 0)
        self.assertEquals(provider.apis, [])

    def test_with_inline_swagger_apis(self):

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": make_swagger(self.input_apis)
                    }
                }
            }
        }

        provider = SamApiProvider(template)
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
                        "Type": "AWS::Serverless::Api",
                        "Properties": {
                            "StageName": "Prod",
                            "DefinitionUri": filename
                        }
                    }
                }
            }

            provider = SamApiProvider(template)
            assertCountEqual(self, self.input_apis, provider.apis)

    @patch("samcli.commands.local.lib.sam_api_provider.SamSwaggerReader")
    def test_with_swagger_as_both_body_and_uri(self, SamSwaggerReaderMock):

        body = {"some": "body"}
        filename = "somefile.txt"

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionUri": filename,
                        "DefinitionBody": body
                    }
                }
            }
        }

        SamSwaggerReaderMock.return_value.read.return_value = make_swagger(self.input_apis)

        cwd = "foo"
        provider = SamApiProvider(template, cwd=cwd)
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
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": make_swagger(apis)
                    }
                }
            }
        }

        provider = SamApiProvider(template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_with_binary_media_types(self):

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionBody": make_swagger(self.input_apis, binary_media_types=self.binary_types)
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

        provider = SamApiProvider(template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_with_binary_media_types_in_swagger_and_on_resource(self):

        input_apis = [
            Api(path="/path", method="OPTIONS", function_name="SamFunc1"),
        ]
        extra_binary_types = ["text/html"]

        template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "BinaryMediaTypes": extra_binary_types,
                        "StageName": "Prod",
                        "DefinitionBody": make_swagger(input_apis, binary_media_types=self.binary_types)
                    }
                }
            }
        }

        expected_binary_types = sorted(self.binary_types + extra_binary_types)
        expected_apis = [
            Api(path="/path", method="OPTIONS", function_name="SamFunc1", binary_media_types=expected_binary_types),
        ]

        provider = SamApiProvider(template)
        assertCountEqual(self, expected_apis, provider.apis)


class TestSamApiProviderWithExplicitAndImplicitApis(TestCase):

    def setUp(self):
        self.explicit_apis = [
            Api(path="/path1", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path2", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path3", method="GET", function_name="explicitfunction", cors=None)
        ]

        self.swagger = make_swagger(self.explicit_apis)

        self.template = {
            "Resources": {

                "Api1": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                    }
                },

                "ImplicitFunc": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "/usr/foo/bar",
                        "Runtime": "nodejs4.3",
                        "Handler": "index.handler"
                    }
                }
            }
        }

    def test_must_union_implicit_and_explicit(self):

        events = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    "Path": "/path1",
                    "Method": "POST"
                }
            },

            "Event2": {
                "Type": "Api",
                "Properties": {
                    "Path": "/path2",
                    "Method": "POST"
                }
            },

            "Event3": {
                "Type": "Api",
                "Properties": {
                    "Path": "/path3",
                    "Method": "POST"
                }
            }
        }

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = self.swagger
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = events

        expected_apis = [
            # From Explicit APIs
            Api(path="/path1", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path2", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path3", method="GET", function_name="explicitfunction", cors=None),
            # From Implicit APIs
            Api(path="/path1", method="POST", function_name="ImplicitFunc", cors=None),
            Api(path="/path2", method="POST", function_name="ImplicitFunc", cors=None),
            Api(path="/path3", method="POST", function_name="ImplicitFunc", cors=None)
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_must_prefer_implicit_api_over_explicit(self):

        implicit_apis = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    # This API is duplicated between implicit & explicit
                    "Path": "/path1",
                    "Method": "get"
                }
            },

            "Event2": {
                "Type": "Api",
                "Properties": {
                    "Path": "/path2",
                    "Method": "POST"
                }
            }
        }

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = self.swagger
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = implicit_apis

        expected_apis = [
            Api(path="/path1", method="GET", function_name="ImplicitFunc", cors=None),  # Comes from Implicit

            Api(path="/path2", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path2", method="POST", function_name="ImplicitFunc", cors=None),  # Comes from implicit

            Api(path="/path3", method="GET", function_name="explicitfunction", cors=None),
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_must_prefer_implicit_with_any_method(self):

        implicit_apis = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    # This API is duplicated between implicit & explicit
                    "Path": "/path",
                    "Method": "ANY"
                }
            }
        }

        explicit_apis = [
            # Explicit should be over masked completely by implicit, because of "ANY"
            Api(path="/path", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path", method="DELETE", function_name="explicitfunction", cors=None),
        ]

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = make_swagger(explicit_apis)
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = implicit_apis

        expected_apis = [
            Api(path="/path", method="GET", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="POST", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="PUT", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="DELETE", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="HEAD", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="OPTIONS", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="PATCH", function_name="ImplicitFunc", cors=None)
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_with_any_method_on_both(self):

        implicit_apis = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    # This API is duplicated between implicit & explicit
                    "Path": "/path",
                    "Method": "ANY"
                }
            },
            "Event2": {
                "Type": "Api",
                "Properties": {
                    # This API is duplicated between implicit & explicit
                    "Path": "/path2",
                    "Method": "GET"
                }
            }
        }

        explicit_apis = [
            # Explicit should be over masked completely by implicit, because of "ANY"
            Api(path="/path", method="ANY", function_name="explicitfunction", cors=None),
            Api(path="/path2", method="POST", function_name="explicitfunction", cors=None),
        ]

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = make_swagger(explicit_apis)
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = implicit_apis

        expected_apis = [
            Api(path="/path", method="GET", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="POST", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="PUT", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="DELETE", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="HEAD", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="OPTIONS", function_name="ImplicitFunc", cors=None),
            Api(path="/path", method="PATCH", function_name="ImplicitFunc", cors=None),

            Api(path="/path2", method="GET", function_name="ImplicitFunc", cors=None),
            Api(path="/path2", method="POST", function_name="explicitfunction", cors=None)
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_must_add_explicit_api_when_ref_with_rest_api_id(self):

        events = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    "Path": "/newpath1",
                    "Method": "POST",
                    "RestApiId": "Api1"  # This path must get added to this API
                }
            },

            "Event2": {
                "Type": "Api",
                "Properties": {
                    "Path": "/newpath2",
                    "Method": "POST",
                    "RestApiId": {"Ref": "Api1"}  # This path must get added to this API
                }
            }
        }

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = self.swagger
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = events

        expected_apis = [
            # From Explicit APIs
            Api(path="/path1", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path2", method="GET", function_name="explicitfunction", cors=None),
            Api(path="/path3", method="GET", function_name="explicitfunction", cors=None),
            # From Implicit APIs
            Api(path="/newpath1", method="POST", function_name="ImplicitFunc", cors=None),
            Api(path="/newpath2", method="POST", function_name="ImplicitFunc", cors=None)
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_both_apis_must_get_binary_media_types(self):

        events = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    "Path": "/newpath1",
                    "Method": "POST"
                }
            },

            "Event2": {
                "Type": "Api",
                "Properties": {
                    "Path": "/newpath2",
                    "Method": "POST"
                }
            }
        }

        # Binary type for implicit
        self.template["Globals"] = {
            "Api": {
                "BinaryMediaTypes": ["image~1gif", "image~1png"]
            }
        }
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = events

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = self.swagger
        # Binary type for explicit
        self.template["Resources"]["Api1"]["Properties"]["BinaryMediaTypes"] = ["explicit/type1", "explicit/type2"]

        # Because of Globals, binary types will be concatenated on the explicit API
        expected_explicit_binary_types = ["explicit/type1", "explicit/type2", "image/gif", "image/png"]
        expected_implicit_binary_types = ["image/gif", "image/png"]

        expected_apis = [
            # From Explicit APIs
            Api(path="/path1", method="GET", function_name="explicitfunction",
                binary_media_types=expected_explicit_binary_types),
            Api(path="/path2", method="GET", function_name="explicitfunction",
                binary_media_types=expected_explicit_binary_types),
            Api(path="/path3", method="GET", function_name="explicitfunction",
                binary_media_types=expected_explicit_binary_types),
            # From Implicit APIs
            Api(path="/newpath1", method="POST", function_name="ImplicitFunc",
                binary_media_types=expected_implicit_binary_types),
            Api(path="/newpath2", method="POST", function_name="ImplicitFunc",
                binary_media_types=expected_implicit_binary_types)
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)

    def test_binary_media_types_with_rest_api_id_reference(self):

        events = {
            "Event1": {
                "Type": "Api",
                "Properties": {
                    "Path": "/connected-to-explicit-path",
                    "Method": "POST",
                    "RestApiId": "Api1"
                }
            },

            "Event2": {
                "Type": "Api",
                "Properties": {
                    "Path": "/true-implicit-path",
                    "Method": "POST"
                }
            }
        }

        # Binary type for implicit
        self.template["Globals"] = {
            "Api": {
                "BinaryMediaTypes": ["image~1gif", "image~1png"]
            }
        }
        self.template["Resources"]["ImplicitFunc"]["Properties"]["Events"] = events

        self.template["Resources"]["Api1"]["Properties"]["DefinitionBody"] = self.swagger
        # Binary type for explicit
        self.template["Resources"]["Api1"]["Properties"]["BinaryMediaTypes"] = ["explicit/type1", "explicit/type2"]

        # Because of Globals, binary types will be concatenated on the explicit API
        expected_explicit_binary_types = ["explicit/type1", "explicit/type2", "image/gif", "image/png"]
        expected_implicit_binary_types = ["image/gif", "image/png"]

        expected_apis = [
            # From Explicit APIs
            Api(path="/path1", method="GET", function_name="explicitfunction",
                binary_media_types=expected_explicit_binary_types),
            Api(path="/path2", method="GET", function_name="explicitfunction",
                binary_media_types=expected_explicit_binary_types),
            Api(path="/path3", method="GET", function_name="explicitfunction",
                binary_media_types=expected_explicit_binary_types),

            # Because of the RestApiId, Implicit APIs will also get the binary media types inherited from
            # the corresponding Explicit API
            Api(path="/connected-to-explicit-path", method="POST", function_name="ImplicitFunc",
                binary_media_types=expected_explicit_binary_types),

            # This is still just a true implicit API because it does not have RestApiId property
            Api(path="/true-implicit-path", method="POST", function_name="ImplicitFunc",
                binary_media_types=expected_implicit_binary_types)
        ]

        provider = SamApiProvider(self.template)
        assertCountEqual(self, expected_apis, provider.apis)


def make_swagger(apis, binary_media_types=None):
    """
    Given a list of API configurations named tuples, returns a Swagger document

    Parameters
    ----------
    apis : list of samcli.commands.local.lib.provider.Api
    binary_media_types : list of str

    Returns
    -------
    dict
        Swagger document

    """
    swagger = {
        "paths": {
        }
    }

    for api in apis:
        swagger["paths"].setdefault(api.path, {})

        integration = {
            "x-amazon-apigateway-integration": {
                "type": "aws_proxy",
                "uri": "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:123456789012:function:{}/invocations".format(api.function_name)  # NOQA
            }
        }

        method = api.method
        if method.lower() == "any":
            method = "x-amazon-apigateway-any-method"

        swagger["paths"][api.path][method] = integration

    if binary_media_types:
        swagger["x-amazon-apigateway-binary-media-types"] = binary_media_types

    return swagger
