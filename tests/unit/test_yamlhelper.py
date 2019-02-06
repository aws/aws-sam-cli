"""
Helper to be able to parse/dump YAML files
"""
import re
from collections import OrderedDict

from unittest import TestCase
from samcli.yamlhelper import yaml_parse, yaml_dump


class TestYaml(TestCase):

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
            "Key1": {
                "Ref": "Something"
            },
            "Key2": {
                "Fn::GetAtt": ["Another", "Arn"]
            },
            "Key3": {
                "Fn::FooBar": [
                    {"Fn::Baz": "YetAnother"},
                    "hello"
                ]
            },
            "Key4": {
                "Fn::SomeTag": {
                    "a": "1"
                }
            },
            "Key5": {
                "Fn::GetAtt": ["OneMore", "Outputs.Arn"]
            },
            "Key6": {
                "Condition": "OtherCondition"
            }
        }
    }

    def test_yaml_with_tags(self):
        output = yaml_parse(self.yaml_with_tags)
        self.assertEquals(self.parsed_yaml_dict, output)

        # Make sure formatter and parser work well with each other
        formatted_str = yaml_dump(output)
        output_again = yaml_parse(formatted_str)
        self.assertEquals(output, output_again)

    def test_yaml_getatt(self):
        # This is an invalid syntax for !GetAtt. But make sure the code does not crash when we encouter this syntax
        # Let CloudFormation interpret this value at runtime
        input = """
        Resource:
            Key: !GetAtt ["a", "b"]
        """

        output = {
            "Resource": {
                "Key": {
                    "Fn::GetAtt": ["a", "b"]
                }
            }
        }

        actual_output = yaml_parse(input)
        self.assertEquals(actual_output, output)

    def test_parse_json_with_tabs(self):
        template = '{\n\t"foo": "bar"\n}'
        output = yaml_parse(template)
        self.assertEqual(output, {'foo': 'bar'})

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
        expected_dict = OrderedDict([
            ('B_Resource', OrderedDict([('Key2', {'Name': 'name2'}), ('Key1', {'Name': 'name1'})])),
            ('A_Resource', OrderedDict([('Key2', {'Name': 'name2'}), ('Key1', {'Name': 'name1'})]))
        ])
        output_dict = yaml_parse(input_template)
        self.assertEqual(expected_dict, output_dict)

    def test_parse_yaml_preserve_elements_order(self):
        input_template = """
        B_Resource:
            Key2:
                Name: name2
            Key1:
                Name: name1
        A_Resource:
            Key2:
                Name: name2
            Key1:
                Name: name1
        """
        output_dict = yaml_parse(input_template)
        expected_dict = OrderedDict([
            ('B_Resource', OrderedDict([('Key2', {'Name': 'name2'}), ('Key1', {'Name': 'name1'})])),
            ('A_Resource', OrderedDict([('Key2', {'Name': 'name2'}), ('Key1', {'Name': 'name1'})]))
        ])
        self.assertEqual(expected_dict, output_dict)

        output_template = yaml_dump(output_dict)
        # yaml dump changes indentation, remove spaces and new line characters to just compare the text
        self.assertEqual(re.sub(r'\n|\s', '', input_template),
                         re.sub(r'\n|\s', '', output_template))
