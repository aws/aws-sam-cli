
import os
import copy
import yaml

from unittest import TestCase
from mock import patch, mock_open
from parameterized import parameterized, param

from samcli.commands._utils.template import get_template_data, _RESOURCES_WITH_LOCAL_PATHS, _update_relative_paths, \
    move_template


class Test_get_template_data(TestCase):

    def test_must_raise_if_file_does_not_exist(self):
        filename = "filename"

        with self.assertRaises(ValueError) as exception_ctx:
            get_template_data(filename)

        ex = exception_ctx.exception
        self.assertEquals(str(ex), "Template file not found at {}".format(filename))

    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_read_file_and_parse(self, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"
        parse_result = "parse result"

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.return_value = parse_result

        with patch("samcli.commands._utils.template.open", m):
            result = get_template_data(filename)

            self.assertEquals(result, parse_result)

        m.assert_called_with(filename, 'r')
        yaml_parse_mock.assert_called_with(file_data)

    @parameterized.expand([
        param(ValueError()),
        param(yaml.YAMLError())
    ])
    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_raise_on_parse_errors(self, exception, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.side_effect = exception

        with patch("samcli.commands._utils.template.open", m):

            with self.assertRaises(ValueError) as ex_ctx:
                get_template_data(filename)

            actual_exception = ex_ctx.exception
            self.assertTrue(str(actual_exception).startswith("Failed to parse template: "))


class Test_update_relative_paths(TestCase):

    def setUp(self):

        self.s3path = "s3://foo/bar"
        self.abspath = os.path.abspath("tosomefolder")
        self.curpath = os.path.join("foo", "bar")
        self.src = os.path.abspath("src")  # /path/from/root/src
        self.dest = os.path.abspath(os.path.join("src", "destination"))  # /path/from/root/src/destination

        self.expected_result = os.path.join("..", "foo", "bar")

    @parameterized.expand(
        [(resource_type, props) for resource_type, props in _RESOURCES_WITH_LOCAL_PATHS.items()]
    )
    def test_must_update_relative_paths(self, resource_type, properties):

        for propname in properties:

            template_dict = {
                "Resources": {
                    "MyResourceWithRelativePath": {
                        "Type": resource_type,
                        "Properties": {
                            propname: self.curpath
                        }
                    },
                    "MyResourceWithS3Path": {
                        "Type": resource_type,
                        "Properties": {
                            propname: self.s3path
                        }
                    },
                    "MyResourceWithAbsolutePath": {
                        "Type": resource_type,
                        "Properties": {
                            propname: self.abspath
                        }
                    },
                    "MyResourceWithInvalidPath": {
                        "Type": resource_type,
                        "Properties": {
                            # Path is not a string
                            propname: {"foo": "bar"}
                        }
                    },
                    "MyResourceWithoutProperties": {
                        "Type": resource_type
                    },
                    "UnsupportedResourceType": {
                        "Type": "AWS::Ec2::Instance",
                        "Properties": {
                            "Code": "bar"
                        }
                    },
                    "ResourceWithoutType": {"foo": "bar"},
                },
                "Parameters": {
                    "a": "b"
                }
            }

            expected_template_dict = copy.deepcopy(template_dict)
            expected_template_dict["Resources"]["MyResourceWithRelativePath"]["Properties"][propname] = \
                self.expected_result

            result = _update_relative_paths(template_dict, self.src, self.dest)

            self.maxDiff = None
            self.assertEquals(result, expected_template_dict)

    def test_must_update_aws_include_also(self):
        template_dict = {
            "Resources": {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.curpath}}},
            "list_prop": [
                "a",
                1, 2, 3,
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.curpath}}},

                # S3 path
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.s3path}}},
            ],
            "Fn::Transform": {"Name": "AWS::OtherTransform"},
            "key1": {"Fn::Transform": "Invalid value"},
            "key2": {"Fn::Transform": {"no": "name"}}
        }

        expected_template_dict = {
            "Resources": {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.expected_result}}},
            "list_prop": [
                "a",
                1, 2, 3,
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.expected_result}}},
                # S3 path
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.s3path}}},
            ],
            "Fn::Transform": {"Name": "AWS::OtherTransform"},
            "key1": {"Fn::Transform": "Invalid value"},
            "key2": {"Fn::Transform": {"no": "name"}}
        }

        result = _update_relative_paths(template_dict, self.src, self.dest)
        self.maxDiff = None
        self.assertEquals(result, expected_template_dict)


class Test_move_template(TestCase):

    @patch("samcli.commands._utils.template._update_relative_paths")
    @patch("samcli.commands._utils.template.yaml_dump")
    def test_must_update_and_write_template(self,
                                            yaml_dump_mock,
                                            update_relative_paths_mock):
        template_dict = {"a": "b"}

        # Moving from /tmp/original/root/template.yaml to /tmp/new/root/othertemplate.yaml
        source = os.path.join("/", "tmp", "original", "root", "template.yaml")
        dest = os.path.join("/", "tmp", "new", "root", "othertemplate.yaml")

        modified_template = update_relative_paths_mock.return_value = "modified template"
        dumped_yaml = yaml_dump_mock.return_value = "dump result"

        m = mock_open()
        with patch("samcli.commands._utils.template.open", m):
            move_template(source, dest, template_dict)

        update_relative_paths_mock.assert_called_once_with(template_dict,
                                                           os.path.dirname(source),
                                                           os.path.dirname(dest))
        yaml_dump_mock.assert_called_with(modified_template)
        m.assert_called_with(dest, 'w')
        m.return_value.write.assert_called_with(dumped_yaml)
