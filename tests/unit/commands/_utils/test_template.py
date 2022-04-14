import copy
import os
import tempfile
from unittest import TestCase
from unittest.mock import patch, mock_open, MagicMock
import shutil

import yaml
from botocore.utils import set_value_from_jmespath
from parameterized import parameterized, param

from samcli.lib.utils.resources import AWS_SERVERLESS_FUNCTION, AWS_SERVERLESS_API, RESOURCES_WITH_IMAGE_COMPONENT
from samcli.commands._utils.template import (
    get_template_data,
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_LOCAL_PATHS,
    _update_relative_paths,
    _resolve_relative_to,
    move_template,
    get_template_parameters,
    TemplateNotFoundException,
    TemplateFailedParsingException,
    get_template_artifacts_format,
    get_template_function_resource_ids,
)
from samcli.lib.utils.packagetype import IMAGE, ZIP


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

    @patch("samcli.commands._utils.template.yaml_parse")
    @patch("samcli.commands._utils.template.pathlib")
    def test_must_read_file_get_and_normalize_parameters(self, pathlib_mock, yaml_parse_mock):
        filename = "filename"
        file_data = "contents of the file"
        parse_result = {
            "Parameters": {
                "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3VersionKeyA3EB644B": {
                    "Type": "String",
                    "Description": 'S3 bucket for asset "12345432"',
                },
            },
            "Resources": {
                "CDKMetadata": {
                    "Type": "AWS::CDK::Metadata",
                    "Properties": {"Analytics": "v2:deflate64:H4s"},
                    "Metadata": {"aws:cdk:path": "Stack/CDKMetadata/Default"},
                },
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {
                        "aws:asset:path": "new path",
                        "aws:asset:property": "Code",
                        "aws:asset:is-bundled": False,
                    },
                },
            },
        }

        pathlib_mock.Path.return_value.exists.return_value = True  # Fake that the file exists

        m = mock_open(read_data=file_data)
        yaml_parse_mock.return_value = parse_result

        with patch("samcli.commands._utils.template.open", m):
            result = get_template_parameters(filename)

            self.assertEqual(
                result,
                {
                    "AssetParametersb9866fd422d32492c62394e8c406ab4004f0c80364bab4957e67e31cf1130481S3VersionKeyA3EB644B": {
                        "Type": "String",
                        "Description": 'S3 bucket for asset "12345432"',
                        "Default": " ",
                    }
                },
            )

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
        self.image_uri = "func12343:latest"

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

    @parameterized.expand([(resource_type, props) for resource_type, props in RESOURCES_WITH_LOCAL_PATHS.items()])
    def test_must_update_relative_resource_metadata_paths(self, resource_type, properties):
        for propname in properties:
            template_dict = {
                "Resources": {
                    "MyResourceWithRelativePath": {
                        "Type": resource_type,
                        "Properties": {},
                        "Metadata": {"aws:asset:path": self.curpath},
                    },
                    "MyResourceWithS3Path": {
                        "Type": resource_type,
                        "Properties": {propname: self.s3path},
                        "Metadata": {},
                    },
                    "MyResourceWithAbsolutePath": {
                        "Type": resource_type,
                        "Properties": {propname: self.abspath},
                        "Metadata": {"aws:asset:path": self.abspath},
                    },
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

            expected_template_dict["Resources"]["MyResourceWithRelativePath"]["Metadata"][
                "aws:asset:path"
            ] = self.expected_result

            result = _update_relative_paths(template_dict, self.src, self.dest)

            self.maxDiff = None
            self.assertEqual(result, expected_template_dict)

    @parameterized.expand([(resource_type, props) for resource_type, props in RESOURCES_WITH_IMAGE_COMPONENT.items()])
    def test_must_skip_image_components(self, resource_type, properties):
        for propname in properties:
            template_dict = {
                "Resources": {
                    "ImageResource": {"Type": resource_type, "Properties": {"PackageType": "Image"}},
                }
            }

            set_value_from_jmespath(template_dict, f"Resources.ImageResource.Properties.{propname}", self.image_uri)

            expected_template_dict = copy.deepcopy(template_dict)

            result = _update_relative_paths(template_dict, self.src, self.dest)

            self.maxDiff = None
            self.assertEqual(result, expected_template_dict)

    @parameterized.expand(
        [
            (image_resource_type, image_props, non_image_resource_type, non_image_props)
            for image_resource_type, image_props in RESOURCES_WITH_IMAGE_COMPONENT.items()
            for non_image_resource_type, non_image_props in RESOURCES_WITH_LOCAL_PATHS.items()
        ]
    )
    def test_must_skip_only_image_components_and_update_relative_resource_paths(
        self, image_resource_type, image_properties, non_image_resource_type, non_image_properties
    ):
        for non_image_propname in non_image_properties:
            for image_propname in image_properties:
                template_dict = {
                    "Resources": {
                        "MyResourceWithRelativePath": {"Type": non_image_resource_type, "Properties": {}},
                        "MyResourceWithS3Path": {
                            "Type": non_image_resource_type,
                            "Properties": {non_image_propname: self.s3path},
                        },
                        "MyResourceWithAbsolutePath": {
                            "Type": non_image_resource_type,
                            "Properties": {non_image_propname: self.abspath},
                        },
                        "MyResourceWithInvalidPath": {
                            "Type": non_image_resource_type,
                            "Properties": {
                                # Path is not a string
                                non_image_propname: {"foo": "bar"}
                            },
                        },
                        "MyResourceWithoutProperties": {"Type": non_image_resource_type},
                        "UnsupportedResourceType": {"Type": "AWS::Ec2::Instance", "Properties": {"Code": "bar"}},
                        "ResourceWithoutType": {"foo": "bar"},
                        "ImageResource": {"Type": image_resource_type, "Properties": {"PackageType": "Image"}},
                    },
                    "Parameters": {"a": "b"},
                }

                set_value_from_jmespath(
                    template_dict, f"Resources.MyResourceWithRelativePath.Properties.{non_image_propname}", self.curpath
                )

                set_value_from_jmespath(
                    template_dict, f"Resources.ImageResource.Properties.{image_propname}", self.image_uri
                )

                expected_template_dict = copy.deepcopy(template_dict)

                set_value_from_jmespath(
                    expected_template_dict,
                    f"Resources.MyResourceWithRelativePath.Properties.{non_image_propname}",
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


class Test_resolve_relative_to(TestCase):
    def setUp(self):
        self.scratchdir = os.path.split(tempfile.mkdtemp(dir=os.curdir))[-1]
        self.curpath = os.path.join("foo", "bar")

    def tearDown(self):
        shutil.rmtree(self.scratchdir)

    def test_must_resolve_relative_to_with_simple_paths(self):
        original_root = os.path.abspath("src")
        new_root = os.path.abspath("src/destination")

        result = _resolve_relative_to(self.curpath, original_root, new_root)
        expected_result = os.path.join("..", self.curpath)

        self.assertEqual(result, expected_result)

    def test_must_resolve_relative_to_with_symlinked_original_root(self):
        original_root = os.path.abspath(os.path.join(self.scratchdir, "some", "src"))
        original_root_link = os.path.abspath(os.path.join(self.scratchdir, "originallink"))
        self.create_symlink(original_root, original_root_link)

        new_root = os.path.abspath("destination")

        result = _resolve_relative_to(self.curpath, original_root_link, new_root)
        # path = foo/bar
        # original_path = /path/from/root/scratchdir/originallink -> /path/from/root/scratchdir/some/src
        # new_path = /path/from/root/destination
        # relative path must be ../scratchdir/some/src/foo/bar
        expected_result = os.path.join("..", self.scratchdir, "some", "src", self.curpath)

        self.assertEqual(result, expected_result)

    def test_must_resolve_relative_to_with_symlinked_new_root(self):
        original_root = os.path.abspath("src")

        new_root = os.path.abspath(os.path.join(self.scratchdir, "some", "destination"))
        new_root_link = os.path.abspath(os.path.join(self.scratchdir, "newlink"))
        self.create_symlink(new_root, new_root_link)

        result = _resolve_relative_to(self.curpath, original_root, new_root_link)
        # path = foo/bar
        # original_path = /path/from/root/src
        # new_path = /path/from/root/scratchdir/newlink -> /path/from/root/scratchdir/some/destination
        # relative path must be ../../../src/foo/bar
        expected_result = os.path.join("..", "..", "..", "src", self.curpath)

        self.assertEqual(result, expected_result)

    def test_must_resolve_relative_to_symlinked_original_root_and_new_root(self):
        original_root = os.path.abspath(os.path.join(self.scratchdir, "some", "src"))
        original_root_link = os.path.abspath(os.path.join(self.scratchdir, "originallink"))
        self.create_symlink(original_root, original_root_link)

        new_root = os.path.abspath(os.path.join(self.scratchdir, "another", "destination"))
        new_root_link = os.path.abspath(os.path.join(self.scratchdir, "newlink"))
        self.create_symlink(new_root, new_root_link)

        result = _resolve_relative_to(self.curpath, original_root, new_root_link)
        # path = foo/bar
        # original_path = /path/from/root/scratchdir/originallink -> /path/from/root/scratchdir/some/src
        # new_path = /path/from/root/scratchdir/newlink -> /path/from/root/scratchdir/another/destination
        # relative path must be ../../some/srcfoo/bar
        expected_result = os.path.join("..", "..", "some", "src", self.curpath)

        self.assertEqual(result, expected_result)

    def create_symlink(self, src, dest):
        os.makedirs(src)
        os.symlink(src, dest)


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


class Test_get_template_artifacts_format(TestCase):
    @patch("samcli.commands._utils.template.get_template_data")
    def test_template_get_artifacts_format(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {
                "HelloWorldFunction1": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {"ImageUri": "myimage", "PackageType": IMAGE},
                },
                "HelloWorldFunction2": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {"CodeUri": "mycode", "PackageType": ZIP},
                },
            }
        }
        self.assertEqual(get_template_artifacts_format(MagicMock()), [IMAGE, ZIP])

    @patch("samcli.commands._utils.template.get_template_data")
    def test_template_get_artifacts_format_non_packageable(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {
                "HelloWorldFunction1": {
                    "Type": "SomeType",
                    "Properties": {"ImageUri": "myimage", "PackageType": IMAGE},
                },
            }
        }
        self.assertEqual(get_template_artifacts_format(MagicMock()), [])

    @patch("samcli.commands._utils.template.get_template_data")
    def test_template_get_artifacts_format_only_image(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {
                "HelloWorldFunction1": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {"ImageUri": "myimage", "PackageType": IMAGE},
                },
            }
        }
        self.assertEqual(get_template_artifacts_format(MagicMock()), [IMAGE])

    @patch("samcli.commands._utils.template.get_template_data")
    def test_template_get_artifacts_format_only_image_other_resources_present(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {
                "HelloWorldFunction1": {
                    "Type": AWS_SERVERLESS_FUNCTION,
                    "Properties": {"ImageUri": "myimage", "PackageType": IMAGE},
                },
                "HelloWorldFunction2": {"Type": AWS_SERVERLESS_API, "Properties": {"StageName": "Prod"}},
            }
        }
        self.assertEqual(get_template_artifacts_format(MagicMock()), [IMAGE])

    @patch("samcli.commands._utils.template.get_template_data")
    def test_template_get_artifacts_format_none_other_resources_present(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {"HelloWorldFunction2": {"Type": AWS_SERVERLESS_API, "Properties": {"StageName": "Prod"}}}
        }
        self.assertEqual(get_template_artifacts_format(MagicMock()), [])


class Test_get_template_function_resouce_ids(TestCase):
    @patch("samcli.commands._utils.template.get_template_data")
    def test_get_template_function_resouce_ids(self, mock_get_template_data):
        mock_get_template_data.return_value = {
            "Resources": {
                "HelloWorldFunction1": {"Type": "AWS::Lambda::Function", "Properties": {"PackageType": IMAGE}},
                "HelloWorldFunction2": {"Type": "AWS::Serverless::Function", "Properties": {"PackageType": ZIP}},
            }
        }
        self.assertEqual(get_template_function_resource_ids(MagicMock(), IMAGE), ["HelloWorldFunction1"])
