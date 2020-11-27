import os
import copy

import jmespath
import yaml
from botocore.utils import set_value_from_jmespath

from unittest import TestCase
from unittest.mock import patch, mock_open, MagicMock
from parameterized import parameterized, param

from samcli.commands._utils.template import (
    get_template_data,
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_LOCAL_PATHS,
    _update_relative_paths,
    _transform_dict,
    move_template,
    get_template_parameters,
    TemplateNotFoundException,
    TemplateFailedParsingException,
)


class Test_get_template_data(TestCase):
    def test_must_raise_if_file_does_not_exist(self):
        filename = "filename"

        with self.assertRaises(TemplateNotFoundException) as exception_ctx:
            get_template_data(filename)

        ex = exception_ctx.exception
        self.assertEqual(str(ex), "Template file not found at {}".format(filename))

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

            self.assertEqual(result, parse_result)

        m.assert_called_with(filename, "r", encoding="utf-8")
        yaml_parse_mock.assert_called_with(file_data)

    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_read_file_and_get_parameters(self, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"
        parse_result = {"Parameters": {"Myparameter": "String"}}

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.return_value = parse_result

        with patch("samcli.commands._utils.template.open", m):
            result = get_template_parameters(filename)

            self.assertEqual(result, {"Myparameter": "String"})

        m.assert_called_with(filename, "r", encoding="utf-8")
        yaml_parse_mock.assert_called_with(file_data)

    @parameterized.expand([param(ValueError()), param(yaml.YAMLError())])
    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_raise_on_parse_errors(self, exception, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.side_effect = exception

        with patch("samcli.commands._utils.template.open", m):

            with self.assertRaises(TemplateFailedParsingException) as ex_ctx:
                get_template_data(filename)

            actual_exception = ex_ctx.exception
            self.assertTrue(str(actual_exception).startswith("Failed to parse template: "))

    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_read_file_with_non_utf8_encoding(self, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "utf-8 😐"
        parse_result = "parse result"
        default_locale_encoding = "cp932"

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        yaml_parse_mock.return_value = parse_result

        # mock open with a different default encoding
        def mock_encoding_open(
            file, mode="r", buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None
        ):
            if encoding is None:
                encoding = default_locale_encoding
            mock_file = MagicMock()

            def mock_read():
                return file_data.encode("utf-8").decode(encoding)

            # __enter__ is used for with open(...) PEP343
            mock_file.__enter__.return_value = mock_file
            mock_file.read = mock_read
            return mock_file

        with patch("samcli.commands._utils.template.open", mock_encoding_open):
            result = get_template_data(filename)
            self.assertEqual(result, parse_result)

        yaml_parse_mock.assert_called_with(file_data)


class Test_update_relative_paths(TestCase):
    def setUp(self):

        self.s3path = "s3://foo/bar"
        self.s3_full_url_https = "https://s3.amazonaws.com/examplebucket/exampletemplate.yml"
        self.s3_full_url_http = "http://s3.amazonaws.com/examplebucket/exampletemplate.yml"
        self.abspath = os.path.abspath("tosomefolder")
        self.curpath = os.path.join("foo", "bar")
        self.src = os.path.abspath("src")  # /path/from/root/src
        self.dest = os.path.abspath(os.path.join("src", "destination"))  # /path/from/root/src/destination

        self.expected_result = os.path.join("..", "foo", "bar")

    @parameterized.expand([(resource_type, props) for resource_type, props in METADATA_WITH_LOCAL_PATHS.items()])
    def test_must_update_relative_metadata_paths(self, resource_type, properties):

        for propname in properties:
            for path in [self.s3path, self.abspath, self.curpath, self.s3_full_url_https, self.s3_full_url_http]:
                template_dict = {
                    "Metadata": {resource_type: {propname: path}, "AWS::Ec2::Instance": {propname: path}},
                    "Parameters": {"a": "b"},
                }

                expected_template_dict = copy.deepcopy(template_dict)
                if path == self.curpath:
                    expected_template_dict["Metadata"][resource_type][propname] = self.expected_result

                result = _update_relative_paths(template_dict, self.src, self.dest)

                self.maxDiff = None
                self.assertEqual(result, expected_template_dict)

    @parameterized.expand([(resource_type, props) for resource_type, props in RESOURCES_WITH_LOCAL_PATHS.items()])
    def test_must_update_relative_resource_paths(self, resource_type, properties):
        for propname in properties:
            template_dict = {
                "Resources": {
                    "MyResourceWithRelativePath": {"Type": resource_type, "Properties": {}},
                    "MyResourceWithS3Path": {"Type": resource_type, "Properties": {propname: self.s3path}},
                    "MyResourceWithAbsolutePath": {"Type": resource_type, "Properties": {propname: self.abspath}},
                    "MyResourceWithInvalidPath": {
                        "Type": resource_type,
                        "Properties": {
                            # Path is not a string
                            propname: {"foo": "bar"}
                        },
                    },
                    "MyResourceWithoutProperties": {"Type": resource_type},
                    "UnsupportedResourceType": {"Type": "AWS::Ec2::Instance", "Properties": {"Code": "bar"}},
                    "ResourceWithoutType": {"foo": "bar"},
                },
                "Parameters": {"a": "b"},
            }

            set_value_from_jmespath(
                template_dict, f"Resources.MyResourceWithRelativePath.Properties.{propname}", self.curpath
            )

            expected_template_dict = copy.deepcopy(template_dict)

            set_value_from_jmespath(
                expected_template_dict,
                f"Resources.MyResourceWithRelativePath.Properties.{propname}",
                self.expected_result,
            )

            result = _update_relative_paths(template_dict, self.src, self.dest)

            self.maxDiff = None
            self.assertEqual(result, expected_template_dict)

    def test_must_update_aws_include_also(self):
        template_dict = {
            "Resources": {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.curpath}}},
            "list_prop": [
                "a",
                1,
                2,
                3,
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.curpath}}},
                # S3 path
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.s3path}}},
            ],
            "Fn::Transform": {"Name": "AWS::OtherTransform"},
            "key1": {"Fn::Transform": "Invalid value"},
            "key2": {"Fn::Transform": {"no": "name"}},
        }

        expected_template_dict = {
            "Resources": {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.expected_result}}},
            "list_prop": [
                "a",
                1,
                2,
                3,
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.expected_result}}},
                # S3 path
                {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": self.s3path}}},
            ],
            "Fn::Transform": {"Name": "AWS::OtherTransform"},
            "key1": {"Fn::Transform": "Invalid value"},
            "key2": {"Fn::Transform": {"no": "name"}},
        }

        result = _update_relative_paths(template_dict, self.src, self.dest)
        self.maxDiff = None
        self.assertEqual(result, expected_template_dict)


class Test_move_template(TestCase):
    @patch("samcli.commands._utils.template._update_relative_paths")
    @patch("samcli.commands._utils.template.yaml_dump")
    def test_must_update_and_write_template(self, yaml_dump_mock, update_relative_paths_mock):
        template_dict = {"a": "b"}

        # Moving from /tmp/original/root/template.yaml to /tmp/new/root/othertemplate.yaml
        source = os.path.join("/", "tmp", "original", "root", "template.yaml")
        dest = os.path.join("/", "tmp", "new", "root", "othertemplate.yaml")

        modified_template = update_relative_paths_mock.return_value = "modified template"
        dumped_yaml = yaml_dump_mock.return_value = "dump result"

        m = mock_open()
        with patch("samcli.commands._utils.template.open", m):
            move_template(source, dest, template_dict)

        update_relative_paths_mock.assert_called_once_with(
            template_dict, os.path.dirname(source), os.path.dirname(dest)
        )
        yaml_dump_mock.assert_called_with(modified_template)
        m.assert_called_with(dest, "w")
        m.return_value.write.assert_called_with(dumped_yaml)


class Test_dict_transformation(TestCase):
    def dummy_transformation(self, original_dict, original_path, property_name, value, context):
        return "foo %s=%s bar" % (property_name, value)

    def test_no_tranformation(self):
        template_dict = {"a": "b", "c": "d"}

        result = _transform_dict(template_dict, "b", self.dummy_transformation)

        self.assertEqual(result, template_dict)

    def test_non_nested_tranformation(self):
        template_dict = {"a": "b", "c": "d"}
        expected_dict = {"a": "foo a=b bar", "c": "d"}

        result = _transform_dict(template_dict, "a", self.dummy_transformation)

        self.assertEqual(result, expected_dict)

    def test_nested_tranformation(self):
        template_dict = {"a": {"b": "c"}}
        expected_dict = {"a": {"b": "foo b=c bar"}}

        result = _transform_dict(template_dict, "a.b", self.dummy_transformation)

        self.assertEqual(result, expected_dict)

    def test_list_tranformation(self):
        template_dict = {"a": {"b": [{"c": "d"}, {"c": "e"}]}}
        expected_dict = {"a": {"b": [{"c": "foo c=d bar"}, {"c": "foo c=e bar"}]}}

        result = _transform_dict(template_dict, "a.b.c", self.dummy_transformation)

        self.assertEqual(result, expected_dict)
