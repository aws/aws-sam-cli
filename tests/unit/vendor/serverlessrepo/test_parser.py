import re
from collections import OrderedDict
from unittest import TestCase

from samcli.vendor.serverlessrepo.exceptions import ApplicationMetadataNotFoundError
from samcli.vendor.serverlessrepo.application_metadata import ApplicationMetadata
import samcli.vendor.serverlessrepo.parser as parser


class TestParser(TestCase):

    yaml_with_tags = """
    Resource:
        Key1: !Ref Something
        Key2: !GetAtt Another.Arn
        Key3: !FooBar [!Baz YetAnother, "hello"]
        Key4: !SomeTag {"a": "1"}
        Key5: !GetAtt OneMore.Outputs.Arn
        Key6: !Condition OtherCondition
    """

    parsed_yaml_dict = {
        "Resource": {
            "Key1": {"Ref": "Something"},
            "Key2": {"Fn::GetAtt": ["Another", "Arn"]},
            "Key3": {"Fn::FooBar": [{"Fn::Baz": "YetAnother"}, "hello"]},
            "Key4": {"Fn::SomeTag": {"a": "1"}},
            "Key5": {"Fn::GetAtt": ["OneMore", "Outputs.Arn"]},
            "Key6": {"Condition": "OtherCondition"},
        }
    }

    def test_yaml_getatt(self):
        # This is an invalid syntax for !GetAtt. But make sure the code does not crash when we encouter this syntax
        # Let CloudFormation interpret this value at runtime
        input_str = """
        Resource:
            Key: !GetAtt ["a", "b"]
        """

        output_dir = {"Resource": {"Key": {"Fn::GetAtt": ["a", "b"]}}}

        actual_output = parser.parse_template(input_str)
        self.assertEqual(actual_output, output_dir)

    def test_parse_json_with_tabs(self):
        template = '{\n\t"foo": "bar"\n}'
        output = parser.parse_template(template)
        self.assertEqual(output, {"foo": "bar"})

    def test_parse_json_preserve_elements_order(self):
        input_template = """
        {
            "B_Resource": {
                "Key2": {
                    "Name": "name2"
                },
                "Key1": {
                    "Name": "name1"
                }
            },
            "A_Resource": {
                "Key2": {
                    "Name": "name2"
                },
                "Key1": {
                    "Name": "name1"
                }
            }
        }
        """
        expected_dict = OrderedDict(
            [
                ("B_Resource", OrderedDict([("Key2", {"Name": "name2"}), ("Key1", {"Name": "name1"})])),
                ("A_Resource", OrderedDict([("Key2", {"Name": "name2"}), ("Key1", {"Name": "name1"})])),
            ]
        )
        output_dict = parser.parse_template(input_template)
        self.assertEqual(expected_dict, output_dict)

    def test_get_app_metadata_missing_metadata(self):
        template_dict_without_metadata = {"RandomKey": {"Key1": "Something"}}
        with self.assertRaises(ApplicationMetadataNotFoundError) as context:
            parser.get_app_metadata(template_dict_without_metadata)

        message = str(context.exception)
        expected = "missing AWS::ServerlessRepo::Application section in template Metadata"
        self.assertTrue(expected in message)

    def test_get_app_metadata_missing_app_metadata(self):
        template_dict_without_app_metadata = {"Metadata": {"Key1": "Something"}}
        with self.assertRaises(ApplicationMetadataNotFoundError) as context:
            parser.get_app_metadata(template_dict_without_app_metadata)

        message = str(context.exception)
        expected = "missing AWS::ServerlessRepo::Application section in template Metadata"
        self.assertTrue(expected in message)

    def test_get_app_metadata_return_metadata(self):
        app_metadata = {"Name": "name", "Description": "description", "Author": "author"}

        template_dict = {"Metadata": {"AWS::ServerlessRepo::Application": dict(app_metadata)}}

        expected = ApplicationMetadata(app_metadata)
        actual = parser.get_app_metadata(template_dict)
        self.assertEqual(expected, actual)

    def test_parse_application_id_aws_partition(self):
        application_id = "arn:aws:serverlessrepo:us-east-1:123456789012:applications/test-app"
        text_with_application_id = "Application with id {} already exists.".format(application_id)
        result = parser.parse_application_id(text_with_application_id)
        self.assertEqual(result, application_id)

    def test_parse_application_id_aws_cn_partition(self):
        application_id = "arn:aws-cn:serverlessrepo:cn-northwest-1:123456789012:applications/test-app"
        text_with_application_id = "Application with id {} already exists.".format(application_id)
        result = parser.parse_application_id(text_with_application_id)
        self.assertEqual(result, application_id)

    def test_parse_application_id_aws_us_gov_partition(self):
        application_id = "arn:aws-us-gov:serverlessrepo:us-gov-east-1:123456789012:applications/test-app"
        text_with_application_id = "Application with id {} already exists.".format(application_id)
        result = parser.parse_application_id(text_with_application_id)
        self.assertEqual(result, application_id)

    def test_parse_application_id_return_none(self):
        text_without_application_id = "text without application id"
        result = parser.parse_application_id(text_without_application_id)
        self.assertIsNone(result)

    def test_strip_app_metadata_when_input_does_not_contain_metadata(self):
        template_dict = {"Resources": {}}
        actual_output = parser.strip_app_metadata(template_dict)
        self.assertEqual(actual_output, template_dict)

    def test_strip_app_metadata_when_metadata_only_contains_app_metadata(self):
        template_dict = {
            "Metadata": {"AWS::ServerlessRepo::Application": {}},
            "Resources": {},
        }
        expected_output = {"Resources": {}}
        actual_output = parser.strip_app_metadata(template_dict)
        self.assertEqual(actual_output, expected_output)

    def test_strip_app_metadata_when_metadata_contains_additional_keys(self):
        template_dict = {"Metadata": {"AWS::ServerlessRepo::Application": {}, "AnotherKey": {}}, "Resources": {}}
        expected_output = {"Metadata": {"AnotherKey": {}}, "Resources": {}}
        actual_output = parser.strip_app_metadata(template_dict)
        self.assertEqual(actual_output, expected_output)
