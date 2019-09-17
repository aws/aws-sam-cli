import tempfile
import json
import os
import botocore

from unittest import TestCase
from parameterized import parameterized, param
from unittest.mock import Mock, patch

from samcli.commands.local.lib.swagger.reader import parse_aws_include_transform, SwaggerReader


class TestParseAwsIncludeTransform(TestCase):
    def test_must_return_location(self):

        data = {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": "s3://bucket/swagger.yaml"}}}

        expected = "s3://bucket/swagger.yaml"
        result = parse_aws_include_transform(data)

        self.assertEqual(result, expected)

    @parameterized.expand(
        [
            param({}),
            param(None),
            param({"Name": "AWS::Include", "Parameters": {"Location": "s3://bucket/swagger.yaml"}}),
            param(
                {
                    "Fn::Transform": {
                        "Name": "AWS::SomeTransformName",
                        "Parameters": {"Location": "s3://bucket/swagger.yaml"},
                    }
                }
            ),
        ]
    )
    def test_invalid_aws_include_data(self, data):
        result = parse_aws_include_transform(data)
        self.assertIsNone(result)


class TestSamSwaggerReader_init(TestCase):
    def test_definition_body_and_uri_required(self):

        with self.assertRaises(ValueError):
            SwaggerReader()


class TestSamSwaggerReader_read(TestCase):
    def test_must_read_first_from_definition_body(self):
        body = {"this is": "swagger"}
        uri = "./file.txt"
        expected = {"some": "value"}

        reader = SwaggerReader(definition_body=body, definition_uri=uri)
        reader._download_swagger = Mock()
        reader._read_from_definition_body = Mock()
        reader._read_from_definition_body.return_value = expected

        actual = reader.read()
        self.assertEqual(actual, expected)

        reader._read_from_definition_body.assert_called_with()
        reader._download_swagger.assert_not_called()

    def test_read_from_definition_uri(self):
        uri = "./file.txt"
        expected = {"some": "value"}

        reader = SwaggerReader(definition_uri=uri)
        reader._download_swagger = Mock()
        reader._download_swagger.return_value = expected

        actual = reader.read()
        self.assertEqual(actual, expected)

        reader._download_swagger.assert_called_with(uri)

    def test_must_use_definition_uri_if_body_does_not_exist(self):
        body = {"this is": "swagger"}
        uri = "./file.txt"
        expected = {"some": "value"}

        reader = SwaggerReader(definition_body=body, definition_uri=uri)
        reader._download_swagger = Mock()
        reader._download_swagger.return_value = expected

        # Set the output of reading the definition body to be None
        reader._read_from_definition_body = Mock()
        reader._read_from_definition_body.return_value = None

        actual = reader.read()
        self.assertEqual(actual, expected)

        reader._read_from_definition_body.assert_called_with()
        reader._download_swagger.assert_called_with(uri)


class TestSamSwaggerReader_read_from_definition_body(TestCase):
    @patch("samcli.commands.local.lib.swagger.reader.parse_aws_include_transform")
    def test_must_work_with_include_transform(self, parse_mock):
        body = {"this": "swagger"}
        expected = {"k": "v"}
        location = "some location"

        reader = SwaggerReader(definition_body=body)
        reader._download_swagger = Mock()
        reader._download_swagger.return_value = expected
        parse_mock.return_value = location

        actual = reader._read_from_definition_body()
        self.assertEqual(actual, expected)
        parse_mock.assert_called_with(body)

    @patch("samcli.commands.local.lib.swagger.reader.parse_aws_include_transform")
    def test_must_get_body_directly(self, parse_mock):
        body = {"this": "swagger"}

        reader = SwaggerReader(definition_body=body)
        parse_mock.return_value = None  # No location is returned from aws_include parser

        actual = reader._read_from_definition_body()
        self.assertEqual(actual, body)


class TestSamSwaggerReader_download_swagger(TestCase):
    @patch("samcli.commands.local.lib.swagger.reader.yaml_parse")
    def test_must_download_from_s3_for_s3_locations(self, yaml_parse_mock):
        location = {"Bucket": "mybucket", "Key": "swagger.yaml", "Version": "versionId"}
        swagger_str = "some swagger str"
        expected = "some data"

        reader = SwaggerReader(definition_uri=location)
        reader._download_from_s3 = Mock()
        reader._download_from_s3.return_value = swagger_str
        yaml_parse_mock.return_value = expected

        actual = reader._download_swagger(location)

        self.assertEqual(actual, expected)
        reader._download_from_s3.assert_called_with(location["Bucket"], location["Key"], location["Version"])
        yaml_parse_mock.assert_called_with(swagger_str)

    @patch("samcli.commands.local.lib.swagger.reader.yaml_parse")
    def test_must_skip_non_s3_dictionaries(self, yaml_parse_mock):

        location = {"some": "value"}

        reader = SwaggerReader(definition_uri=location)
        reader._download_from_s3 = Mock()

        actual = reader._download_swagger(location)

        self.assertIsNone(actual)
        reader._download_from_s3.assert_not_called()
        yaml_parse_mock.assert_not_called()

    @patch("samcli.commands.local.lib.swagger.reader.yaml_parse")
    def test_must_read_from_local_file(self, yaml_parse_mock):
        data = {"some": "value"}
        expected = "parsed result"
        yaml_parse_mock.return_value = expected

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            filepath = fp.name

            json.dump(data, fp)
            fp.flush()

            cwd = os.path.dirname(filepath)
            filename = os.path.basename(filepath)

            reader = SwaggerReader(definition_uri=filename, working_dir=cwd)
            actual = reader._download_swagger(filename)

            self.assertEqual(actual, expected)
            yaml_parse_mock.assert_called_with('{"some": "value"}')  # data was read back from the file as JSON string

    @patch("samcli.commands.local.lib.swagger.reader.yaml_parse")
    def test_must_read_from_local_file_without_working_directory(self, yaml_parse_mock):
        data = {"some": "value"}
        expected = "parsed result"
        yaml_parse_mock.return_value = expected

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as fp:
            filepath = fp.name

            json.dump(data, fp)
            fp.flush()

            reader = SwaggerReader(definition_uri=filepath)
            actual = reader._download_swagger(filepath)

            self.assertEqual(actual, expected)
            yaml_parse_mock.assert_called_with('{"some": "value"}')  # data was read back from the file as JSON string

    @patch("samcli.commands.local.lib.swagger.reader.yaml_parse")
    def test_must_return_none_if_file_not_found(self, yaml_parse_mock):
        expected = "parsed result"
        yaml_parse_mock.return_value = expected

        reader = SwaggerReader(definition_uri="somepath")
        actual = reader._download_swagger("abcdefgh.txt")

        self.assertIsNone(actual)
        yaml_parse_mock.assert_not_called()

    def test_with_invalid_location(self):

        reader = SwaggerReader(definition_uri="something")
        actual = reader._download_swagger({})

        self.assertIsNone(actual)


class TestSamSwaggerReaderDownloadFromS3(TestCase):
    def setUp(self):
        self.bucket = "mybucket"
        self.key = "mykey"
        self.version = "versionid"

    @patch("samcli.commands.local.lib.swagger.reader.boto3")
    @patch("samcli.commands.local.lib.swagger.reader.tempfile")
    def test_must_download_file_from_s3(self, tempfilemock, botomock):

        s3_mock = Mock()
        botomock.client.return_value = s3_mock

        fp_mock = Mock()
        tempfilemock.TemporaryFile.return_value.__enter__.return_value = fp_mock  # mocking context manager

        expected = "data from file"
        fp_mock.read.return_value = expected

        actual = SwaggerReader._download_from_s3(self.bucket, self.key, self.version)
        self.assertEqual(actual, expected)

        s3_mock.download_fileobj.assert_called_with(
            self.bucket, self.key, fp_mock, ExtraArgs={"VersionId": self.version}
        )

        fp_mock.seek.assert_called_with(0)  # make sure we seek the file before reading
        fp_mock.read.assert_called_with()

    @patch("samcli.commands.local.lib.swagger.reader.boto3")
    @patch("samcli.commands.local.lib.swagger.reader.tempfile")
    def test_must_fail_on_download_from_s3(self, tempfilemock, botomock):
        s3_mock = Mock()
        botomock.client.return_value = s3_mock

        fp_mock = Mock()
        tempfilemock.TemporaryFile.return_value.__enter__.return_value = fp_mock  # mocking context manager
        s3_mock.download_fileobj.side_effect = botocore.exceptions.ClientError({"Error": {}}, "download_file")

        with self.assertRaises(Exception) as cm:
            SwaggerReader._download_from_s3(self.bucket, self.key)
        self.assertIn(cm.exception.__class__, (botocore.exceptions.NoCredentialsError, botocore.exceptions.ClientError))

    @patch("samcli.commands.local.lib.swagger.reader.boto3")
    @patch("samcli.commands.local.lib.swagger.reader.tempfile")
    def test_must_work_without_object_version_id(self, tempfilemock, botomock):

        s3_mock = Mock()
        botomock.client.return_value = s3_mock

        fp_mock = Mock()
        tempfilemock.TemporaryFile.return_value.__enter__.return_value = fp_mock  # mocking context manager

        expected = "data from file"
        fp_mock.read.return_value = expected

        actual = SwaggerReader._download_from_s3(self.bucket, self.key)
        self.assertEqual(actual, expected)

        s3_mock.download_fileobj.assert_called_with(self.bucket, self.key, fp_mock, ExtraArgs={})

    @patch("samcli.commands.local.lib.swagger.reader.boto3")
    @patch("samcli.commands.local.lib.swagger.reader.tempfile")
    def test_must_log_on_download_exception(self, tempfilemock, botomock):

        s3_mock = Mock()
        botomock.client.return_value = s3_mock

        fp_mock = Mock()
        tempfilemock.TemporaryFile.return_value.__enter__.return_value = fp_mock  # mocking context manager
        s3_mock.download_fileobj.side_effect = botocore.exceptions.ClientError({"Error": {}}, "download_file")

        with self.assertRaises(botocore.exceptions.ClientError):
            SwaggerReader._download_from_s3(self.bucket, self.key)

            fp_mock.read.assert_not_called()


class TestSamSwaggerReader_parse_s3_location(TestCase):
    def setUp(self):
        self.bucket = "mybucket"
        self.key = "mykey"
        self.version = "myversion"

    def test_must_parse_valid_dict(self):
        location = {"Bucket": self.bucket, "Key": self.key, "Version": self.version}

        result = SwaggerReader._parse_s3_location(location)
        self.assertEqual(result, (self.bucket, self.key, self.version))

    def test_must_parse_dict_without_version(self):
        location = {"Bucket": self.bucket, "Key": self.key}

        result = SwaggerReader._parse_s3_location(location)
        self.assertEqual(result, (self.bucket, self.key, None))

    def test_must_parse_s3_uri_string(self):
        location = "s3://{}/{}?versionId={}".format(self.bucket, self.key, self.version)

        result = SwaggerReader._parse_s3_location(location)
        self.assertEqual(result, (self.bucket, self.key, self.version))

    def test_must_parse_s3_uri_string_without_version_id(self):
        location = "s3://{}/{}".format(self.bucket, self.key)

        result = SwaggerReader._parse_s3_location(location)
        self.assertEqual(result, (self.bucket, self.key, None))

    @parameterized.expand(
        [
            param("http://s3.amazonaws.com/bucket/key"),
            param("./foo/bar.txt"),
            param("/home/user/bar.txt"),
            param({"k": "v"}),
        ]
    )
    def test_must_parse_invalid_location(self, location):

        result = SwaggerReader._parse_s3_location(location)
        self.assertEqual(result, (None, None, None))
