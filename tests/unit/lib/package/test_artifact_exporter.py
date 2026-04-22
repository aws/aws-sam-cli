import functools
import json
import os
import platform
import random
import string
import tempfile
import unittest
import zipfile
from contextlib import contextmanager, closing
from typing import Optional, Dict
from unittest import mock
from unittest.mock import call, patch, Mock, MagicMock

from samcli.commands._utils.experimental import ExperimentalFlag
from samcli.commands.package import exceptions
from samcli.commands.package.exceptions import ExportFailedError
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.package.artifact_exporter import (
    is_local_folder,
    make_abs_path,
    Template,
    CloudFormationStackResource,
    CloudFormationStackSetResource,
    ServerlessApplicationResource,
)
from samcli.lib.package.packageable_resources import (
    GraphQLApiCodeResource,
    GraphQLApiSchemaResource,
    is_s3_protocol_url,
    is_local_file,
    upload_local_artifacts,
    Resource,
    ResourceWithS3UrlDict,
    ServerlessApiResource,
    ServerlessFunctionResource,
    GraphQLSchemaResource,
    LambdaFunctionResource,
    ApiGatewayRestApiResource,
    ElasticBeanstalkApplicationVersion,
    LambdaLayerVersionResource,
    copy_to_temp_dir,
    include_transform_export_handler,
    GLOBAL_EXPORT_DICT,
    ServerlessLayerVersionResource,
    ServerlessRepoApplicationLicense,
    ServerlessRepoApplicationReadme,
    AppSyncResolverCodeResource,
    AppSyncResolverRequestTemplateResource,
    AppSyncResolverResponseTemplateResource,
    AppSyncFunctionConfigurationCodeResource,
    AppSyncFunctionConfigurationRequestTemplateResource,
    AppSyncFunctionConfigurationResponseTemplateResource,
    GlueJobCommandScriptLocationResource,
    CloudFormationModuleVersionModulePackage,
    CloudFormationResourceVersionSchemaHandlerPackage,
    ResourceZip,
    ResourceImage,
    ResourceImageDict,
    ECRResource,
)
from samcli.lib.package.permissions import (
    WindowsFilePermissionPermissionMapper,
    WindowsDirPermissionPermissionMapper,
    AdditiveFilePermissionPermissionMapper,
    AdditiveDirPermissionPermissionMapper,
)
from samcli.lib.package.uploaders import Destination
from samcli.lib.package.utils import zip_folder, make_zip, make_zip_with_lambda_permissions, make_zip_with_permissions
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.utils.resources import LAMBDA_LOCAL_RESOURCES, RESOURCES_WITH_LOCAL_PATHS
from tests.testing_utils import FileCreator


class TestArtifactExporter(unittest.TestCase):
    def setUp(self):
        self.s3_uploader_mock = MagicMock()
        self.s3_uploader_mock.s3.meta.endpoint_url = "https://s3.some-valid-region.amazonaws.com"
        self.ecr_uploader_mock = Mock()

        def get_mock(destination: Destination):
            return {Destination.S3: self.s3_uploader_mock, Destination.ECR: self.ecr_uploader_mock}.get(destination)

        self.uploaders_mock = Mock()
        self.uploaders_mock.get.side_effect = get_mock

        self.code_signer_mock = Mock()
        self.code_signer_mock.should_sign_package.return_value = False

        self.graphql_api_local_paths = ["resolvers/createFoo.js", "functions/func1.js", "functions/func2.js"]
        self.graphql_api_resource_dict = {
            "Resolvers": {"Mutation": {"createFoo": {"CodeUri": self.graphql_api_local_paths[0]}}},
            "Functions": {
                "func1": {"CodeUri": self.graphql_api_local_paths[1]},
                "func2": {"CodeUri": self.graphql_api_local_paths[2]},
            },
        }
        self.graphql_api_paths_to_property = [
            "Resolvers.Mutation.createFoo.CodeUri",
            "Functions.func1.CodeUri",
            "Functions.func2.CodeUri",
        ]

    def test_all_resources_export(self):
        uploaded_s3_url = "s3://foo/bar?versionId=baz"

        setup = [
            {"class": ServerlessFunctionResource, "expected_result": uploaded_s3_url},
            {"class": ServerlessApiResource, "expected_result": uploaded_s3_url},
            {"class": GraphQLSchemaResource, "expected_result": uploaded_s3_url},
            {"class": AppSyncResolverCodeResource, "expected_result": uploaded_s3_url},
            {"class": AppSyncResolverRequestTemplateResource, "expected_result": uploaded_s3_url},
            {"class": AppSyncResolverResponseTemplateResource, "expected_result": uploaded_s3_url},
            {"class": AppSyncFunctionConfigurationRequestTemplateResource, "expected_result": uploaded_s3_url},
            {"class": AppSyncFunctionConfigurationResponseTemplateResource, "expected_result": uploaded_s3_url},
            {"class": AppSyncFunctionConfigurationCodeResource, "expected_result": uploaded_s3_url},
            {"class": ApiGatewayRestApiResource, "expected_result": {"Bucket": "foo", "Key": "bar", "Version": "baz"}},
            {
                "class": LambdaFunctionResource,
                "expected_result": {"S3Bucket": "foo", "S3Key": "bar", "S3ObjectVersion": "baz"},
            },
            {"class": ElasticBeanstalkApplicationVersion, "expected_result": {"S3Bucket": "foo", "S3Key": "bar"}},
            {
                "class": LambdaLayerVersionResource,
                "expected_result": {"S3Bucket": "foo", "S3Key": "bar", "S3ObjectVersion": "baz"},
            },
            {"class": ServerlessLayerVersionResource, "expected_result": uploaded_s3_url},
            {"class": ServerlessRepoApplicationReadme, "expected_result": uploaded_s3_url},
            {"class": ServerlessRepoApplicationLicense, "expected_result": uploaded_s3_url},
            {"class": ServerlessRepoApplicationLicense, "expected_result": uploaded_s3_url},
            {"class": GlueJobCommandScriptLocationResource, "expected_result": {"ScriptLocation": uploaded_s3_url}},
            {"class": CloudFormationModuleVersionModulePackage, "expected_result": uploaded_s3_url},
            {"class": CloudFormationResourceVersionSchemaHandlerPackage, "expected_result": uploaded_s3_url},
            {"class": GraphQLApiSchemaResource, "expected_result": uploaded_s3_url},
            {"class": GraphQLApiCodeResource, "expected_result": [uploaded_s3_url, uploaded_s3_url, uploaded_s3_url]},
        ]

        with patch("samcli.lib.package.packageable_resources.upload_local_artifacts") as upload_local_artifacts_mock:
            for test in setup:
                self._helper_verify_export_resources(
                    test["class"], uploaded_s3_url, upload_local_artifacts_mock, test["expected_result"]
                )

    def test_invalid_export_resource(self):
        with patch("samcli.lib.package.packageable_resources.upload_local_artifacts") as upload_local_artifacts_mock:
            s3_uploader_mock = Mock()
            code_signer_mock = Mock()
            upload_local_artifacts_mock.reset_mock()
            resource_obj = ServerlessFunctionResource(uploaders=self.uploaders_mock, code_signer=code_signer_mock)
            resource_id = "id"
            resource_dict = {"InlineCode": "code"}
            parent_dir = "dir"
            resource_obj.export(resource_id, resource_dict, parent_dir)
            upload_local_artifacts_mock.assert_not_called()
            code_signer_mock.should_sign_package.assert_not_called()
            code_signer_mock.sign_package.assert_not_called()

    def _helper_verify_export_resources(
        self, test_class, uploaded_s3_url, upload_local_artifacts_mock, expected_result
    ):
        s3_uploader_mock = Mock()
        code_signer_mock = Mock()
        code_signer_mock.should_sign_package.return_value = False
        upload_local_artifacts_mock.reset_mock()

        uploaders_mock = Mock()
        uploaders_mock.get = Mock(return_value=s3_uploader_mock)

        resource_id = "id"

        if test_class == GraphQLApiCodeResource:
            resource_dict = self.graphql_api_resource_dict
        elif "." in test_class.PROPERTY_NAME:
            reversed_property_names = test_class.PROPERTY_NAME.split(".")
            reversed_property_names.reverse()
            property_dict = {reversed_property_names[0]: "foo"}
            for sub_property_name in reversed_property_names[1:]:
                property_dict = {sub_property_name: property_dict}
            resource_dict = property_dict
        else:
            resource_dict = {test_class.PROPERTY_NAME: "foo"}
        parent_dir = "dir"

        upload_local_artifacts_mock.return_value = uploaded_s3_url

        resource_obj = test_class(uploaders=uploaders_mock, code_signer=code_signer_mock)

        resource_obj.export(resource_id, resource_dict, parent_dir)

        if test_class == GraphQLApiCodeResource:
            upload_local_artifacts_mock.assert_has_calls(
                [
                    call(
                        test_class.RESOURCE_TYPE,
                        resource_id,
                        resource_dict,
                        self.graphql_api_paths_to_property[0],
                        parent_dir,
                        s3_uploader_mock,
                        None,
                        self.graphql_api_local_paths[0],
                        None,
                    ),
                    call(
                        test_class.RESOURCE_TYPE,
                        resource_id,
                        resource_dict,
                        self.graphql_api_paths_to_property[1],
                        parent_dir,
                        s3_uploader_mock,
                        None,
                        self.graphql_api_local_paths[1],
                        None,
                    ),
                    call(
                        test_class.RESOURCE_TYPE,
                        resource_id,
                        resource_dict,
                        self.graphql_api_paths_to_property[2],
                        parent_dir,
                        s3_uploader_mock,
                        None,
                        self.graphql_api_local_paths[2],
                        None,
                    ),
                ],
                any_order=True,
            )
        elif test_class in (
            ApiGatewayRestApiResource,
            LambdaFunctionResource,
            ElasticBeanstalkApplicationVersion,
            LambdaLayerVersionResource,
        ):
            upload_local_artifacts_mock.assert_called_once_with(
                test_class.RESOURCE_TYPE,
                resource_id,
                resource_dict,
                test_class.PROPERTY_NAME,
                parent_dir,
                s3_uploader_mock,
            )
        else:
            upload_local_artifacts_mock.assert_called_once_with(
                test_class.RESOURCE_TYPE,
                resource_id,
                resource_dict,
                test_class.PROPERTY_NAME,
                parent_dir,
                s3_uploader_mock,
                None,
                None,
                None,
            )
        code_signer_mock.sign_package.assert_not_called()
        if test_class == GraphQLApiCodeResource:
            result = [
                self.graphql_api_resource_dict["Resolvers"]["Mutation"]["createFoo"][test_class.PROPERTY_NAME],
                self.graphql_api_resource_dict["Functions"]["func1"][test_class.PROPERTY_NAME],
                self.graphql_api_resource_dict["Functions"]["func2"][test_class.PROPERTY_NAME],
            ]
        elif "." in test_class.PROPERTY_NAME:
            top_level_property_name = test_class.PROPERTY_NAME.split(".")[0]
            result = resource_dict[top_level_property_name]
        else:
            result = resource_dict[test_class.PROPERTY_NAME]
        self.assertEqual(result, expected_result)

    def test_is_s3_url(self):
        valid = [
            "s3://foo/bar",
            "s3://foo/bar/baz/cat/dog",
            "s3://foo/bar?versionId=abc",
            "s3://foo/bar/baz?versionId=abc&versionId=123",
            "s3://foo/bar/baz?versionId=abc",
            "s3://www.amazon.com/foo/bar",
            "s3://my-new-bucket/foo/bar?a=1&a=2&a=3&b=1",
            "https://s3-eu-west-1.amazonaws.com/bucket/key",
            "https://s3.us-east-1.amazonaws.com/bucket/key",
        ]

        invalid = [
            # For purposes of exporter, we need S3 URLs to point to an object
            # and not a bucket
            "s3://foo",
            "https://www.amazon.com",
        ]

        for url in valid:
            self._assert_is_valid_s3_url(url)

        for url in invalid:
            self._assert_is_invalid_s3_url(url)

    def _assert_is_valid_s3_url(self, url):
        self.assertTrue(is_s3_protocol_url(url), "{0} should be valid".format(url))

    def _assert_is_invalid_s3_url(self, url):
        self.assertFalse(is_s3_protocol_url(url), "{0} should be valid".format(url))

    def test_is_local_file(self):
        with tempfile.NamedTemporaryFile() as handle:
            self.assertTrue(is_local_file(handle.name))
            self.assertFalse(is_local_folder(handle.name))

    def test_is_local_folder(self):
        with self.make_temp_dir() as filename:
            self.assertTrue(is_local_folder(filename))
            self.assertFalse(is_local_file(filename))

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_file(self, zip_and_upload_mock):
        # Case 1: Artifact path is a relative path
        # Verifies that we package local artifacts appropriately
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        self.s3_uploader_mock.upload_with_dedup.return_value = expected_s3_url

        with tempfile.NamedTemporaryFile() as handle:
            # Artifact is a file in the temporary directory
            artifact_path = handle.name
            parent_dir = tempfile.gettempdir()

            resource_dict = {property_name: artifact_path}
            result = upload_local_artifacts(
                resource_type, resource_id, resource_dict, property_name, parent_dir, self.s3_uploader_mock
            )
            self.assertEqual(result, expected_s3_url)

            # Internally the method would convert relative paths to absolute
            # path, with respect to the parent directory
            absolute_artifact_path = make_abs_path(parent_dir, artifact_path)
            self.s3_uploader_mock.upload_with_dedup.assert_called_with(absolute_artifact_path)

            zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_file_with_cache(self, zip_and_upload_mock):
        # Case 1: Artifact path is a relative path
        # Verifies that we package local artifacts appropriately
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        with tempfile.NamedTemporaryFile() as handle:
            # Artifact is a file in the temporary directory
            artifact_path = handle.name
            parent_dir = tempfile.gettempdir()
            absolute_artifact_path = make_abs_path(parent_dir, artifact_path)

            resource_dict = {property_name: artifact_path}
            result = upload_local_artifacts(
                resource_type,
                resource_id,
                resource_dict,
                property_name,
                parent_dir,
                self.s3_uploader_mock,
                previously_uploaded={
                    absolute_artifact_path: expected_s3_url,
                    absolute_artifact_path + "wrong path": expected_s3_url + "wrong url",
                },
            )
            self.assertEqual(result, expected_s3_url)

            self.s3_uploader_mock.upload_with_dedup.assert_not_called()
            zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_file_abs_path(self, zip_and_upload_mock):
        # Case 2: Artifact path is an absolute path
        # Verifies that we package local artifacts appropriately
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        self.s3_uploader_mock.upload_with_dedup.return_value = expected_s3_url

        with tempfile.NamedTemporaryFile() as handle:
            parent_dir = tempfile.gettempdir()
            artifact_path = make_abs_path(parent_dir, handle.name)

            resource_dict = {property_name: artifact_path}
            result = upload_local_artifacts(
                resource_type, resource_id, resource_dict, property_name, parent_dir, self.s3_uploader_mock
            )
            self.assertEqual(result, expected_s3_url)

            self.s3_uploader_mock.upload_with_dedup.assert_called_with(artifact_path)
            zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_file_abs_path_with_cache(self, zip_and_upload_mock):
        # Case 2: Artifact path is an absolute path
        # Verifies that we package local artifacts appropriately
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        self.s3_uploader_mock.upload_with_dedup.return_value = expected_s3_url

        with tempfile.NamedTemporaryFile() as handle:
            parent_dir = tempfile.gettempdir()
            artifact_path = make_abs_path(parent_dir, handle.name)

            resource_dict = {property_name: artifact_path}
            result = upload_local_artifacts(
                resource_type,
                resource_id,
                resource_dict,
                property_name,
                parent_dir,
                self.s3_uploader_mock,
                previously_uploaded={
                    artifact_path: expected_s3_url,
                    artifact_path + "wrong path": expected_s3_url + "wrong url",
                },
            )
            self.assertEqual(result, expected_s3_url)

            self.s3_uploader_mock.upload_with_dedup.assert_not_called()
            zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_folder(self, zip_and_upload_mock):
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        zip_and_upload_mock.return_value = expected_s3_url

        #  Artifact path is a Directory
        with self.make_temp_dir() as artifact_path:
            # Artifact is a file in the temporary directory
            parent_dir = tempfile.gettempdir()
            resource_dict = {property_name: artifact_path}

            result = upload_local_artifacts(
                resource_type, resource_id, resource_dict, property_name, parent_dir, Mock()
            )
            self.assertEqual(result, expected_s3_url)

            absolute_artifact_path = make_abs_path(parent_dir, artifact_path)

            zip_and_upload_mock.assert_called_once_with(absolute_artifact_path, mock.ANY, None, zip_method=make_zip)

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_folder_with_cache(self, zip_and_upload_mock):
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        zip_and_upload_mock.return_value = expected_s3_url

        #  Artifact path is a Directory
        with self.make_temp_dir() as artifact_path:
            # Artifact is a file in the temporary directory
            parent_dir = tempfile.gettempdir()
            resource_dict = {property_name: artifact_path}
            absolute_artifact_path = make_abs_path(parent_dir, artifact_path)

            result = upload_local_artifacts(
                resource_type,
                resource_id,
                resource_dict,
                property_name,
                parent_dir,
                Mock(),
                previously_uploaded={
                    absolute_artifact_path: expected_s3_url,
                    absolute_artifact_path + "wrong path": expected_s3_url + "wrong url",
                },
            )
            self.assertEqual(result, expected_s3_url)

            zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_folder_lambda_resources(self, zip_and_upload_mock):
        for resource_type in LAMBDA_LOCAL_RESOURCES:
            property_name = "property"
            resource_id = "resource_id"
            expected_s3_url = "s3://foo/bar?versionId=baz"

            zip_and_upload_mock.return_value = expected_s3_url
            #  Artifact path is a Directory
            with self.make_temp_dir() as artifact_path:
                # Artifact is a file in the temporary directory
                parent_dir = tempfile.gettempdir()
                resource_dict = {property_name: artifact_path}

                result = upload_local_artifacts(
                    resource_type, resource_id, resource_dict, property_name, parent_dir, Mock()
                )
                self.assertEqual(result, expected_s3_url)

                absolute_artifact_path = make_abs_path(parent_dir, artifact_path)
                # zip_method will NOT be the generalized zip_method `make_zip`

                with self.assertRaises(AssertionError):
                    zip_and_upload_mock.assert_called_once_with(
                        absolute_artifact_path, mock.ANY, None, zip_method=make_zip
                    )

                # zip_method will be lambda specific.
                zip_and_upload_mock.assert_called_once_with(
                    absolute_artifact_path, mock.ANY, None, zip_method=make_zip_with_lambda_permissions
                )
                zip_and_upload_mock.reset_mock()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_folder_lambda_resources_with_cache(self, zip_and_upload_mock):
        for resource_type in LAMBDA_LOCAL_RESOURCES:
            property_name = "property"
            resource_id = "resource_id"
            expected_s3_url = "s3://foo/bar?versionId=baz"

            zip_and_upload_mock.return_value = expected_s3_url
            #  Artifact path is a Directory
            with self.make_temp_dir() as artifact_path:
                # Artifact is a file in the temporary directory
                parent_dir = tempfile.gettempdir()
                resource_dict = {property_name: artifact_path}
                absolute_artifact_path = make_abs_path(parent_dir, artifact_path)

                result = upload_local_artifacts(
                    resource_type,
                    resource_id,
                    resource_dict,
                    property_name,
                    parent_dir,
                    Mock(),
                    previously_uploaded={
                        absolute_artifact_path: expected_s3_url,
                        absolute_artifact_path + "wrong path": expected_s3_url + "wrong url",
                    },
                )
                self.assertEqual(result, expected_s3_url)

                zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_folder_non_lambda_resources(self, zip_and_upload_mock):
        non_lambda_resources = RESOURCES_WITH_LOCAL_PATHS.keys() - LAMBDA_LOCAL_RESOURCES
        for resource_type in non_lambda_resources:
            property_name = "property"
            resource_id = "resource_id"
            expected_s3_url = "s3://foo/bar?versionId=baz"

            zip_and_upload_mock.return_value = expected_s3_url
            #  Artifact path is a Directory
            with self.make_temp_dir() as artifact_path:
                # Artifact is a file in the temporary directory
                parent_dir = tempfile.gettempdir()
                resource_dict = {property_name: artifact_path}

                result = upload_local_artifacts(
                    resource_type, resource_id, resource_dict, property_name, parent_dir, Mock()
                )
                self.assertEqual(result, expected_s3_url)

                absolute_artifact_path = make_abs_path(parent_dir, artifact_path)

                # zip_method will NOT be the specialized zip_method `make_zip_with_lambda_permissions`
                with self.assertRaises(AssertionError):
                    zip_and_upload_mock.assert_called_once_with(
                        absolute_artifact_path, mock.ANY, None, zip_method=make_zip_with_lambda_permissions
                    )

                # zip_method will be the generalized zip_method `make_zip`
                zip_and_upload_mock.assert_called_once_with(absolute_artifact_path, mock.ANY, None, zip_method=make_zip)
                zip_and_upload_mock.reset_mock()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_local_folder_non_lambda_resources_with_cache(self, zip_and_upload_mock):
        non_lambda_resources = RESOURCES_WITH_LOCAL_PATHS.keys() - LAMBDA_LOCAL_RESOURCES
        for resource_type in non_lambda_resources:
            property_name = "property"
            resource_id = "resource_id"
            expected_s3_url = "s3://foo/bar?versionId=baz"

            zip_and_upload_mock.return_value = expected_s3_url
            #  Artifact path is a Directory
            with self.make_temp_dir() as artifact_path:
                # Artifact is a file in the temporary directory
                parent_dir = tempfile.gettempdir()
                resource_dict = {property_name: artifact_path}
                absolute_artifact_path = make_abs_path(parent_dir, artifact_path)

                result = upload_local_artifacts(
                    resource_type,
                    resource_id,
                    resource_dict,
                    property_name,
                    parent_dir,
                    Mock(),
                    previously_uploaded={
                        absolute_artifact_path: expected_s3_url,
                        absolute_artifact_path + "wrong path": expected_s3_url + "wrong url",
                    },
                )
                self.assertEqual(result, expected_s3_url)
                zip_and_upload_mock.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_no_path(self, zip_and_upload_mock):
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        zip_and_upload_mock.return_value = expected_s3_url

        # If you don't specify a path, we will default to Current Working Dir
        resource_dict = {}
        parent_dir = tempfile.gettempdir()

        result = upload_local_artifacts(
            resource_type, resource_id, resource_dict, property_name, parent_dir, self.s3_uploader_mock
        )
        self.assertEqual(result, expected_s3_url)

        zip_and_upload_mock.assert_called_once_with(parent_dir, mock.ANY, None, zip_method=make_zip)
        self.s3_uploader_mock.upload_with_dedup.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_no_path_with_cache(self, zip_and_upload_mock):
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        expected_s3_url = "s3://foo/bar?versionId=baz"

        # If you don't specify a path, we will default to Current Working Dir
        resource_dict = {}
        parent_dir = tempfile.gettempdir()

        result = upload_local_artifacts(
            resource_type,
            resource_id,
            resource_dict,
            property_name,
            parent_dir,
            self.s3_uploader_mock,
            previously_uploaded={parent_dir: expected_s3_url, parent_dir + "wrong path": expected_s3_url + "wrong url"},
        )
        self.assertEqual(result, expected_s3_url)

        zip_and_upload_mock.assert_not_called()
        self.s3_uploader_mock.upload_with_dedup.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_s3_url(self, zip_and_upload_mock):
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        object_s3_url = "s3://foo/bar?versionId=baz"

        # If URL is already S3 URL, this will be returned without zip/upload
        resource_dict = {property_name: object_s3_url}
        parent_dir = tempfile.gettempdir()

        result = upload_local_artifacts(
            resource_type, resource_id, resource_dict, property_name, parent_dir, self.s3_uploader_mock
        )
        self.assertEqual(result, object_s3_url)

        zip_and_upload_mock.assert_not_called()
        self.s3_uploader_mock.upload_with_dedup.assert_not_called()

    @patch("samcli.lib.package.utils.zip_and_upload")
    def test_upload_local_artifacts_invalid_value(self, zip_and_upload_mock):
        property_name = "property"
        resource_id = "resource_id"
        resource_type = "resource_type"
        parent_dir = tempfile.gettempdir()

        with self.assertRaises(exceptions.InvalidLocalPathError):
            non_existent_file = "some_random_filename"
            resource_dict = {property_name: non_existent_file}
            upload_local_artifacts(
                resource_type, resource_id, resource_dict, property_name, parent_dir, self.s3_uploader_mock
            )

        with self.assertRaises(exceptions.InvalidLocalPathError):
            non_existent_file = ["invalid datatype"]
            resource_dict = {property_name: non_existent_file}
            upload_local_artifacts(
                resource_type, resource_id, resource_dict, property_name, parent_dir, self.s3_uploader_mock
            )

        zip_and_upload_mock.assert_not_called()
        self.s3_uploader_mock.upload_with_dedup.assert_not_called()

    @patch("samcli.lib.package.utils.make_zip")
    def test_zip_folder(self, make_zip_mock):
        zip_file_name = "name.zip"
        make_zip_mock.return_value = zip_file_name

        with self.make_temp_dir() as dirname:
            with zip_folder(dirname, zip_method=make_zip_mock) as actual_zip_file_name:
                self.assertEqual(actual_zip_file_name, (zip_file_name, mock.ANY))

        make_zip_mock.assert_called_once_with(mock.ANY, dirname)

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_zip(self, upload_local_artifacts_mock):
        # Property value is a path to file

        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "/path/to/file"
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        upload_local_artifacts_mock.return_value = s3_url

        resource.export(resource_id, resource_dict, parent_dir)

        upload_local_artifacts_mock.assert_called_once_with(
            resource.RESOURCE_TYPE,
            resource_id,
            resource_dict,
            resource.PROPERTY_NAME,
            parent_dir,
            self.s3_uploader_mock,
            None,
            None,
            None,
        )

        self.assertEqual(resource_dict[resource.PROPERTY_NAME], s3_url)

        self.s3_uploader_mock.delete_artifact = MagicMock()
        resource.delete(resource_id, resource_dict)
        self.assertEqual(self.s3_uploader_mock.delete_artifact.call_count, 1)

    @patch("samcli.lib.package.packageable_resources.upload_local_image_artifacts")
    def test_resource_lambda_image(self, upload_local_image_artifacts_mock):
        # Property value is a path to an image

        class MockResource(ResourceImage):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, None)

        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "image:latest"
        parent_dir = "dir"
        ecr_url = "123456789.dkr.ecr.us-east-1.amazonaws.com/sam-cli"

        upload_local_image_artifacts_mock.return_value = ecr_url

        resource.export(resource_id, resource_dict, parent_dir)

        upload_local_image_artifacts_mock.assert_called_once_with(
            resource_id, resource_dict, resource.PROPERTY_NAME, parent_dir, self.ecr_uploader_mock
        )

        self.assertEqual(resource_dict[resource.PROPERTY_NAME], ecr_url)

        self.ecr_uploader_mock.delete_artifact = MagicMock()
        resource.delete(resource_id, resource_dict)
        self.assertEqual(self.ecr_uploader_mock.delete_artifact.call_count, 1)

    @patch("samcli.lib.package.packageable_resources.upload_local_image_artifacts")
    def test_resource_image_dict(self, upload_local_image_artifacts_mock):
        # Property value is a path to an image

        class MockResource(ResourceImageDict):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, None)

        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "image:latest"
        parent_dir = "dir"
        ecr_url = "123456789.dkr.ecr.us-east-1.amazonaws.com/sam-cli"

        upload_local_image_artifacts_mock.return_value = ecr_url

        resource.export(resource_id, resource_dict, parent_dir)

        upload_local_image_artifacts_mock.assert_called_once_with(
            resource_id, resource_dict, resource.PROPERTY_NAME, parent_dir, self.ecr_uploader_mock
        )

        self.assertEqual(resource_dict[resource.PROPERTY_NAME][resource.EXPORT_PROPERTY_CODE_KEY], ecr_url)

        self.ecr_uploader_mock.delete_artifact = MagicMock()
        resource.delete(resource_id, resource_dict)
        self.assertEqual(self.ecr_uploader_mock.delete_artifact.call_count, 1)

    def test_lambda_image_resource_package_success(self):
        # Property value is set to an image

        class MockResource(ResourceImage):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, None)

        resource_id = "id"
        resource_dict = {}
        original_image = "image:latest"
        resource_dict[resource.PROPERTY_NAME] = original_image
        parent_dir = "dir"
        ecr_url = "123456789.dkr.ecr.us-east-1.amazonaws.com/sam-cli"
        self.ecr_uploader_mock.upload.return_value = ecr_url

        resource.export(resource_id, resource_dict, parent_dir)

        self.assertEqual(resource_dict[resource.PROPERTY_NAME], ecr_url)

    def test_lambda_image_resource_non_package_image_already_remote(self):
        # Property value is set to an ecr image

        class MockResource(ResourceImage):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, None)

        resource_id = "id"
        resource_dict = {}
        original_image = "123456789.dkr.ecr.us-east-1.amazonaws.com/sam-cli"
        resource_dict[resource.PROPERTY_NAME] = original_image
        parent_dir = "dir"

        resource.export(resource_id, resource_dict, parent_dir)

        self.assertEqual(resource_dict[resource.PROPERTY_NAME], original_image)

    def test_lambda_image_resource_no_image_present(self):
        # Property value is set to an ecr image

        class MockResource(ResourceImage):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, None)

        resource_id = "id"
        resource_dict = {}
        original_image = None
        resource_dict[resource.PROPERTY_NAME] = original_image
        parent_dir = "dir"

        with self.assertRaises(ExportFailedError):
            resource.export(resource_id, resource_dict, parent_dir)

    @patch("shutil.rmtree")
    @patch("zipfile.is_zipfile")
    @patch("samcli.lib.package.packageable_resources.copy_to_temp_dir")
    @patch("samcli.lib.package.utils.zip_and_upload")
    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_resource_with_force_zip_on_regular_file(
        self, is_local_file_mock, zip_and_upload_mock, copy_to_temp_dir_mock, is_zipfile_mock, rmtree_mock
    ):
        # Property value is a path to file and FORCE_ZIP is True

        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"
            FORCE_ZIP = True

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        resource_dict = {}
        original_path = "/path/to/file"
        resource_dict[resource.PROPERTY_NAME] = original_path
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        zip_and_upload_mock.return_value = s3_url
        is_local_file_mock.return_value = True

        with self.make_temp_dir() as tmp_dir:
            copy_to_temp_dir_mock.return_value = tmp_dir

            # This is not a zip file
            is_zipfile_mock.return_value = False

            resource.export(resource_id, resource_dict, parent_dir)

            zip_and_upload_mock.assert_called_once_with(tmp_dir, mock.ANY, None, zip_method=make_zip)
            rmtree_mock.assert_called_once_with(tmp_dir)
            is_zipfile_mock.assert_called_once_with(original_path)
            self.code_signer_mock.should_sign_package.assert_called_once_with(resource_id)
            self.code_signer_mock.sign_package.assert_not_called()
            self.assertEqual(resource_dict[resource.PROPERTY_NAME], s3_url)

    @patch("shutil.rmtree")
    @patch("zipfile.is_zipfile")
    @patch("samcli.lib.package.packageable_resources.copy_to_temp_dir")
    @patch("samcli.lib.package.utils.zip_and_upload")
    @patch("samcli.lib.package.packageable_resources.is_local_file")
    @patch("samcli.lib.package.utils.is_local_file")
    def test_resource_with_force_zip_on_zip_file(
        self,
        is_local_file_mock_utils,
        is_local_file_mock_resources,
        zip_and_upload_mock,
        copy_to_temp_dir_mock,
        is_zipfile_mock,
        rmtree_mock,
    ):
        # Property value is a path to zip file and FORCE_ZIP is True
        # We should *not* re-zip an existing zip

        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"
            FORCE_ZIP = True

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        resource_dict = {}
        original_path = "/path/to/zip_file"
        resource_dict[resource.PROPERTY_NAME] = original_path
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        # When the file is actually a zip-file, no additional zipping has to happen
        is_zipfile_mock.return_value = True
        is_local_file_mock_utils.return_value = True
        is_local_file_mock_resources.return_value = True
        zip_and_upload_mock.return_value = s3_url
        self.s3_uploader_mock.upload_with_dedup.return_value = s3_url

        resource.export(resource_id, resource_dict, parent_dir)

        copy_to_temp_dir_mock.assert_not_called()
        zip_and_upload_mock.assert_not_called()
        rmtree_mock.assert_not_called()
        is_zipfile_mock.assert_called_once_with(original_path)
        self.code_signer_mock.should_sign_package.assert_called_once_with(resource_id)
        self.code_signer_mock.sign_package.assert_not_called()
        self.assertEqual(resource_dict[resource.PROPERTY_NAME], s3_url)

    @patch("shutil.rmtree")
    @patch("zipfile.is_zipfile")
    @patch("samcli.lib.package.utils.copy_to_temp_dir")
    @patch("samcli.lib.package.utils.zip_and_upload")
    @patch("samcli.lib.package.packageable_resources.is_local_file")
    @patch("samcli.lib.package.utils.is_local_file")
    def test_resource_without_force_zip(
        self,
        is_local_file_mock_utils,
        is_local_file_mock_resources,
        zip_and_upload_mock,
        copy_to_temp_dir_mock,
        is_zipfile_mock,
        rmtree_mock,
    ):
        class MockResourceNoForceZip(ResourceZip):
            PROPERTY_NAME = "foo"

        resource = MockResourceNoForceZip(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        resource_dict = {}
        original_path = "/path/to/file"
        resource_dict[resource.PROPERTY_NAME] = original_path
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        # This is not a zip file, but a valid local file. Since FORCE_ZIP is NOT set, this will not be zipped
        is_zipfile_mock.return_value = False
        is_local_file_mock_resources.return_value = True
        is_local_file_mock_utils.return_value = True
        zip_and_upload_mock.return_value = s3_url
        self.s3_uploader_mock.upload_with_dedup.return_value = s3_url

        resource.export(resource_id, resource_dict, parent_dir)

        copy_to_temp_dir_mock.assert_not_called()
        zip_and_upload_mock.assert_not_called()
        rmtree_mock.assert_not_called()
        is_zipfile_mock.assert_called_once_with(original_path)
        self.code_signer_mock.should_sign_package.assert_called_once_with(resource_id)
        self.code_signer_mock.sign_package.assert_not_called()
        self.assertEqual(resource_dict[resource.PROPERTY_NAME], s3_url)

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_empty_property_value(self, upload_local_artifacts_mock):
        # Property value is empty

        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "/path/to/file"
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        upload_local_artifacts_mock.return_value = s3_url
        resource_dict = {}
        resource.export(resource_id, resource_dict, parent_dir)
        upload_local_artifacts_mock.assert_called_once_with(
            resource.RESOURCE_TYPE,
            resource_id,
            resource_dict,
            resource.PROPERTY_NAME,
            parent_dir,
            self.s3_uploader_mock,
            None,
            None,
            None,
        )
        self.code_signer_mock.should_sign_package.assert_called_once_with(resource_id)
        self.code_signer_mock.sign_package.assert_not_called()
        self.assertEqual(resource_dict[resource.PROPERTY_NAME], s3_url)

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_property_value_dict(self, upload_local_artifacts_mock):
        # Property value is a dictionary. Export should not upload anything

        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "/path/to/file"
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        upload_local_artifacts_mock.return_value = s3_url
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = {"a": "b"}
        resource.export(resource_id, resource_dict, parent_dir)
        upload_local_artifacts_mock.assert_not_called()
        self.assertEqual(resource_dict, {"foo": {"a": "b"}})

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_has_package_null_property_to_false(self, upload_local_artifacts_mock):
        # Should not upload anything if PACKAGE_NULL_PROPERTY is set to False

        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"
            PACKAGE_NULL_PROPERTY = False

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        resource_dict = {}
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        upload_local_artifacts_mock.return_value = s3_url

        resource.export(resource_id, resource_dict, parent_dir)

        upload_local_artifacts_mock.assert_not_called()
        self.assertNotIn(resource.PROPERTY_NAME, resource_dict)

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_export_fails(self, upload_local_artifacts_mock):
        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "/path/to/file"
        parent_dir = "dir"
        s3_url = "s3://foo/bar"

        upload_local_artifacts_mock.side_effect = RuntimeError
        resource_dict = {}

        with self.assertRaises(exceptions.ExportFailedError):
            resource.export(resource_id, resource_dict, parent_dir)

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_with_s3_url_dict(self, upload_local_artifacts_mock):
        """
        Checks if we properly export from the Resource classc
        :return:
        """

        self.assertTrue(issubclass(ResourceWithS3UrlDict, Resource))

        class MockResource(ResourceWithS3UrlDict):
            PROPERTY_NAME = "foo"
            BUCKET_NAME_PROPERTY = "b"
            OBJECT_KEY_PROPERTY = "o"
            VERSION_PROPERTY = "v"

        resource = MockResource(self.uploaders_mock, self.code_signer_mock)

        # Case 1: Property value is a path to file
        resource_id = "id"
        resource_dict = {}
        resource_dict[resource.PROPERTY_NAME] = "/path/to/file"
        parent_dir = "dir"
        s3_url = "s3://bucket/key1/key2?versionId=SomeVersionNumber"

        upload_local_artifacts_mock.return_value = s3_url

        resource.export(resource_id, resource_dict, parent_dir)

        upload_local_artifacts_mock.assert_called_once_with(
            resource.RESOURCE_TYPE,
            resource_id,
            resource_dict,
            resource.PROPERTY_NAME,
            parent_dir,
            self.s3_uploader_mock,
        )

        self.assertEqual(
            resource_dict[resource.PROPERTY_NAME], {"b": "bucket", "o": "key1/key2", "v": "SomeVersionNumber"}
        )

        self.s3_uploader_mock.delete_artifact = MagicMock()
        resource.delete(resource_id, resource_dict)
        self.s3_uploader_mock.delete_artifact.assert_called_once_with(remote_path="key1/key2", is_key=True)

    def test_ecr_resource_delete(self):
        # Property value is set to an image

        class MockResource(ECRResource):
            PROPERTY_NAME = "foo"

        resource = MockResource(self.uploaders_mock, None)

        resource_id = "id"
        resource_dict = {}
        repository = "repository"
        resource_dict[resource.PROPERTY_NAME] = repository

        self.ecr_uploader_mock.delete_ecr_repository = Mock()

        resource.delete(resource_id, resource_dict)

        self.ecr_uploader_mock.delete_ecr_repository.assert_called_once_with(physical_id="repository")

    @patch("samcli.lib.package.packageable_resources.upload_local_artifacts")
    def test_resource_with_signing_configuration(self, upload_local_artifacts_mock):
        class MockResource(ResourceZip):
            PROPERTY_NAME = "foo"

        code_signer_mock = Mock()
        code_signer_mock.should_sign_package.return_value = True
        code_signer_mock.sign_package.return_value = "signed_s3_location"
        upload_local_artifacts_mock.return_value = "non_signed_s3_location"

        resource = MockResource(self.uploaders_mock, code_signer_mock)

        resource_id = "id"
        resource_dict = {resource.PROPERTY_NAME: "/path/to/file"}
        parent_dir = "dir"
        resource.export(resource_id, resource_dict, parent_dir)
        self.assertEqual(resource_dict[resource.PROPERTY_NAME], "signed_s3_location")

    @patch("samcli.lib.package.artifact_exporter.Template")
    def test_export_cloudformation_stack(self, TemplateMock):
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        exported_template_dict = {"foo": "bar"}
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"

        template_instance_mock = Mock()
        TemplateMock.return_value = template_instance_mock
        template_instance_mock.export.return_value = exported_template_dict

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        handle = tempfile.NamedTemporaryFile(delete=False)
        try:
            template_path = handle.name
            handle.close()
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            stack_resource.export(resource_id, resource_dict, parent_dir)

            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)

            TemplateMock.assert_called_once_with(
                template_path,
                parent_dir,
                self.uploaders_mock,
                self.code_signer_mock,
                normalize_parameters=True,
                normalize_template=True,
                parent_stack_id="id",
                parameter_values=mock.ANY,
            )
            template_instance_mock.export.assert_called_once_with()
            self.s3_uploader_mock.upload.assert_called_once_with(mock.ANY, mock.ANY)
            self.s3_uploader_mock.to_path_style_s3_url.assert_called_once_with("world", None)
        finally:
            os.remove(template_path)

    def test_export_cloudformation_stack_no_upload_path_is_s3url(self):
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "s3://hello/world"
        resource_dict = {property_name: s3_url}

        # Case 1: Path is already S3 url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_no_upload_path_is_httpsurl(self):
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "https://s3.amazonaws.com/hello/world"
        resource_dict = {property_name: s3_url}

        # Case 1: Path is already S3 url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_no_upload_path_is_s3_region_httpsurl(self):
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME

        s3_url = "https://s3.some-valid-region.amazonaws.com/hello/world"
        resource_dict = {property_name: s3_url}

        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_no_upload_path_is_empty(self):
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "s3://hello/world"
        resource_dict = {property_name: s3_url}

        # Case 2: Path is empty
        resource_dict = {}
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict, {})
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_no_upload_path_not_file(self):
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "s3://hello/world"

        # Case 3: Path is not a file
        with self.make_temp_dir() as dirname:
            resource_dict = {property_name: dirname}
            with self.assertRaises(exceptions.ExportFailedError):
                stack_resource.export(resource_id, resource_dict, "dir")
                self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_set(self):
        stack_resource = CloudFormationStackSetResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        with tempfile.NamedTemporaryFile(delete=False) as handle:
            template_path = handle.name
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            stack_resource.export(resource_id, resource_dict, parent_dir)
            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)

            self.s3_uploader_mock.upload.assert_called_once_with(mock.ANY, mock.ANY)
            self.s3_uploader_mock.to_path_style_s3_url.assert_called_once_with("world", None)

    def test_export_cloudformation_stack_set_no_upload_path_is_s3url(self):
        stack_resource = CloudFormationStackSetResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "s3://hello/world"
        resource_dict = {property_name: s3_url}
        # Case 1: Path is already S3 url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_set_no_upload_path_is_httpsurl(self):
        stack_resource = CloudFormationStackSetResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "https://s3.amazonaws.com/hello/world"
        resource_dict = {property_name: s3_url}
        # Case 2: Path is already HTTPS S3 url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_set_no_upload_path_is_s3_region_httpsurl(self):
        stack_resource = CloudFormationStackSetResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "https://s3.some-valid-region.amazonaws.com/hello/world"
        resource_dict = {property_name: s3_url}
        # Case 3: Path is already HTTPS S3 Regional url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_set_no_upload_path_is_empty(self):
        stack_resource = CloudFormationStackSetResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        # Case 4: Path is empty
        resource_dict = {}
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict, {})
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_cloudformation_stack_set_no_upload_path_not_file(self):
        stack_resource = CloudFormationStackSetResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        # Case 5: Path is not a file
        with self.make_temp_dir() as dirname:
            resource_dict = {property_name: dirname}
            with self.assertRaises(exceptions.ExportFailedError):
                stack_resource.export(resource_id, resource_dict, "dir")
                self.s3_uploader_mock.upload.assert_not_called()

    @patch("samcli.lib.package.artifact_exporter.Template")
    def test_export_serverless_application(self, TemplateMock):
        stack_resource = ServerlessApplicationResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        exported_template_dict = {"foo": "bar"}
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"

        template_instance_mock = Mock()
        TemplateMock.return_value = template_instance_mock
        template_instance_mock.export.return_value = exported_template_dict

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        handle = tempfile.NamedTemporaryFile(delete=False)
        try:
            template_path = handle.name
            handle.close()
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            stack_resource.export(resource_id, resource_dict, parent_dir)

            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)

            TemplateMock.assert_called_once_with(
                template_path,
                parent_dir,
                self.uploaders_mock,
                self.code_signer_mock,
                normalize_parameters=True,
                normalize_template=True,
                parent_stack_id="id",
                parameter_values=mock.ANY,
            )
            template_instance_mock.export.assert_called_once_with()
            self.s3_uploader_mock.upload.assert_called_once_with(mock.ANY, mock.ANY)
            self.s3_uploader_mock.to_path_style_s3_url.assert_called_once_with("world", None)
        finally:
            os.remove(template_path)

    def test_export_serverless_application_no_upload_path_is_s3url(self):
        stack_resource = ServerlessApplicationResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "s3://hello/world"
        resource_dict = {property_name: s3_url}

        # Case 1: Path is already S3 url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_serverless_application_no_upload_path_is_httpsurl(self):
        stack_resource = ServerlessApplicationResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME
        s3_url = "https://s3.amazonaws.com/hello/world"
        resource_dict = {property_name: s3_url}

        # Case 1: Path is already S3 url
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], s3_url)
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_serverless_application_no_upload_path_is_empty(self):
        stack_resource = ServerlessApplicationResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME

        # Case 2: Path is empty
        resource_dict = {}
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict, {})
        self.s3_uploader_mock.upload.assert_not_called()

    def test_export_serverless_application_no_upload_path_not_file(self):
        stack_resource = ServerlessApplicationResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME

        # Case 3: Path is not a file
        with self.make_temp_dir() as dirname:
            resource_dict = {property_name: dirname}
            with self.assertRaises(exceptions.ExportFailedError):
                stack_resource.export(resource_id, resource_dict, "dir")
                self.s3_uploader_mock.upload.assert_not_called()

    def test_export_serverless_application_no_upload_path_is_dictionary(self):
        stack_resource = ServerlessApplicationResource(self.uploaders_mock, self.code_signer_mock)
        resource_id = "id"
        property_name = stack_resource.PROPERTY_NAME

        # Case 4: Path is dictionary
        location = {"ApplicationId": "id", "SemanticVersion": "1.0.1"}
        resource_dict = {property_name: location}
        stack_resource.export(resource_id, resource_dict, "dir")
        self.assertEqual(resource_dict[property_name], location)
        self.s3_uploader_mock.upload.assert_not_called()

    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_template_export_metadata(self, yaml_parse_mock):
        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        metadata_type1_class = Mock()
        metadata_type1_class.RESOURCE_TYPE = "metadata_type1"
        metadata_type1_class.PROPERTY_NAME = "property_1"
        metadata_type1_class.ARTIFACT_TYPE = ZIP
        metadata_type1_class.EXPORT_DESTINATION = Destination.S3

        metadata_type1_instance = Mock()
        metadata_type1_class.return_value = metadata_type1_instance

        metadata_type2_class = Mock()
        metadata_type2_class.RESOURCE_TYPE = "metadata_type2"
        metadata_type2_class.PROPERTY_NAME = "property_2"
        metadata_type2_class.ARTIFACT_TYPE = ZIP
        metadata_type2_class.EXPORT_DESTINATION = Destination.S3
        metadata_type2_instance = Mock()
        metadata_type2_class.return_value = metadata_type2_instance

        metadata_to_export = [metadata_type1_class, metadata_type2_class]

        template_dict = {"Metadata": {"metadata_type1": {"property_1": "abc"}, "metadata_type2": {"property_2": "def"}}}
        open_mock = mock.mock_open()
        yaml_parse_mock.return_value = template_dict

        # Patch the file open method to return template string
        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            template_exporter = Template(
                template_path,
                parent_dir,
                self.uploaders_mock,
                self.code_signer_mock,
                metadata_to_export=metadata_to_export,
            )
            exported_template = template_exporter.export()
            self.assertEqual(exported_template, template_dict)

            open_mock.assert_called_once_with(make_abs_path(parent_dir, template_path), "r", encoding="utf-8")

            self.assertEqual(1, yaml_parse_mock.call_count)

            metadata_type1_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock)
            metadata_type1_instance.export.assert_called_once_with("metadata_type1", mock.ANY, template_dir)
            metadata_type2_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock)
            metadata_type2_instance.export.assert_called_once_with("metadata_type2", mock.ANY, template_dir)

    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_template_export(self, yaml_parse_mock):
        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "resource_type1"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance
        resource_type2_class = Mock()
        resource_type2_class.RESOURCE_TYPE = "resource_type2"
        resource_type2_class.ARTIFACT_TYPE = ZIP
        resource_type2_class.EXPORT_DESTINATION = Destination.S3
        resource_type2_instance = Mock()
        resource_type2_class.return_value = resource_type2_instance

        resources_to_export = [resource_type1_class, resource_type2_class]

        properties = {"foo": "bar"}
        template_dict = {
            "Resources": {
                "Resource1": {"Type": "resource_type1", "Properties": properties},
                "Resource2": {"Type": "resource_type2", "Properties": properties},
                "Resource3": {"Type": "some-other-type", "Properties": properties},
            }
        }

        open_mock = mock.mock_open()
        yaml_parse_mock.return_value = template_dict

        # Patch the file open method to return template string
        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            template_exporter = Template(
                template_path, parent_dir, self.uploaders_mock, self.code_signer_mock, resources_to_export
            )
            exported_template = template_exporter.export()
            self.assertEqual(exported_template, template_dict)

            open_mock.assert_called_once_with(make_abs_path(parent_dir, template_path), "r", encoding="utf-8")

            self.assertEqual(1, yaml_parse_mock.call_count)

            resource_type1_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock, None)
            resource_type1_instance.export.assert_called_once_with("Resource1", mock.ANY, template_dir)
            resource_type2_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock, None)
            resource_type2_instance.export.assert_called_once_with("Resource2", mock.ANY, template_dir)

    @patch("samcli.lib.package.artifact_exporter.is_experimental_enabled")
    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_template_export_with_experimental_flag(self, yaml_parse_mock, is_experimental_enabled_mock):

        is_experimental_enabled_mock.side_effect = lambda *args: {
            (ExperimentalFlag.PackagePerformance,): True,
        }.get(args, False)

        _cache: Optional[Dict] = None

        def mock_class_init_function(mock_instance):
            def init_cache(uploaders, code_signer, cache):
                nonlocal _cache
                if _cache is None:
                    _cache = cache
                return mock_instance

            return init_cache

        def mock_export_function(cache_key, cache_value):
            def export_set_cache(*args):
                nonlocal _cache
                _cache[cache_key] = cache_value

            return export_set_cache

        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "resource_type1"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_instance.export.side_effect = mock_export_function("key1", "value1")
        resource_type1_class.side_effect = mock_class_init_function(resource_type1_instance)
        resource_type2_class = Mock()
        resource_type2_class.RESOURCE_TYPE = "resource_type2"
        resource_type2_class.ARTIFACT_TYPE = ZIP
        resource_type2_class.EXPORT_DESTINATION = Destination.S3
        resource_type2_instance = Mock()
        resource_type2_instance.export.side_effect = mock_export_function("key2", "value2")
        resource_type2_class.side_effect = mock_class_init_function(resource_type2_instance)

        resources_to_export = [resource_type1_class, resource_type2_class]

        properties = {"foo": "bar"}
        template_dict = {
            "Resources": {
                "Resource1": {"Type": "resource_type1", "Properties": properties},
                "Resource2": {"Type": "resource_type2", "Properties": properties},
                "Resource3": {"Type": "some-other-type", "Properties": properties},
            }
        }

        open_mock = mock.mock_open()
        yaml_parse_mock.return_value = template_dict

        # Patch the file open method to return template string
        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            template_exporter = Template(
                template_path, parent_dir, self.uploaders_mock, self.code_signer_mock, resources_to_export
            )
            exported_template = template_exporter.export()
            self.assertEqual(exported_template, template_dict)

            open_mock.assert_called_once_with(make_abs_path(parent_dir, template_path), "r", encoding="utf-8")

            self.assertEqual(1, yaml_parse_mock.call_count)

            resource_type1_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock, mock.ANY)
            resource_type1_instance.export.assert_called_once_with("Resource1", mock.ANY, template_dir)
            resource_type2_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock, mock.ANY)
            resource_type2_instance.export.assert_called_once_with("Resource2", mock.ANY, template_dir)

        self.assertEqual({"key1": "value1", "key2": "value2"}, _cache)

    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_cdk_template_export(self, yaml_parse_mock):
        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "AWS::Lambda::Function"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance

        resources_to_export = [resource_type1_class]

        template_dict = {
            "Resources": {
                "Resource1": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "S3Bucket": "bucket_name",
                            "S3Key": "key_name",
                        },
                    },
                    "Metadata": {
                        "aws:cdk:path": "Stack/Resource1/Resource",
                        "aws:asset:path": "/path/code",
                        "aws:asset:is-bundled": False,
                        "aws:asset:property": "Code",
                    },
                },
            }
        }

        open_mock = mock.mock_open()
        yaml_parse_mock.return_value = template_dict

        # Patch the file open method to return template string
        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            template_exporter = Template(
                template_path,
                parent_dir,
                self.uploaders_mock,
                self.code_signer_mock,
                resources_to_export,
                normalize_template=True,
            )
            exported_template = template_exporter.export()
            self.assertEqual(exported_template, template_dict)

            open_mock.assert_called_once_with(make_abs_path(parent_dir, template_path), "r", encoding="utf-8")

            self.assertEqual(1, yaml_parse_mock.call_count)

            resource_type1_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock, None)
            expected_resource_properties = {
                "Code": "/path/code",
            }
            resource_type1_instance.export.assert_called_once_with(
                "Resource1", expected_resource_properties, template_dir
            )

    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_cdk_template_export_with_normalize_parameter(self, yaml_parse_mock):
        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "AWS::Lambda::Function"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance

        resources_to_export = [resource_type1_class]

        template_dict = {
            "Parameters": {
                "AssetParameters123": {"Type": "String", "Description": 'S3 bucket for asset "12345432"'},
            },
            "Resources": {
                "Resource1": {
                    "Type": "AWS::Lambda::Function",
                    "Properties": {
                        "Code": {
                            "S3Bucket": "bucket_name",
                            "S3Key": "key_name",
                        },
                    },
                    "Metadata": {
                        "aws:cdk:path": "Stack/Resource1/Resource",
                        "aws:asset:path": "/path/code",
                        "aws:asset:is-bundled": False,
                        "aws:asset:property": "Code",
                    },
                },
            },
        }

        open_mock = mock.mock_open()
        yaml_parse_mock.return_value = template_dict

        # Patch the file open method to return template string
        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            template_exporter = Template(
                template_path,
                parent_dir,
                self.uploaders_mock,
                self.code_signer_mock,
                resources_to_export,
                normalize_template=True,
                normalize_parameters=True,
            )
            exported_template = template_exporter.export()
            template_dict["Parameters"]["AssetParameters123"]["Default"] = " "
            self.assertEqual(exported_template, template_dict)

            open_mock.assert_called_once_with(make_abs_path(parent_dir, template_path), "r", encoding="utf-8")

            self.assertEqual(1, yaml_parse_mock.call_count)

            resource_type1_class.assert_called_once_with(self.uploaders_mock, self.code_signer_mock, None)
            expected_resource_properties = {
                "Code": "/path/code",
            }
            resource_type1_instance.export.assert_called_once_with(
                "Resource1", expected_resource_properties, template_dir
            )

    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_template_export_with_globals(self, yaml_parse_mock):
        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "resource_type1"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance
        resource_type2_class = Mock()
        resource_type2_class.RESOURCE_TYPE = "resource_type2"
        resource_type2_class.ARTIFACT_TYPE = ZIP
        resource_type2_class.EXPORT_DESTINATION = Destination.S3
        resource_type2_instance = Mock()
        resource_type2_class.return_value = resource_type2_instance

        resources_to_export = [resource_type1_class, resource_type2_class]

        properties = {"foo": "bar"}
        template_dict = {
            "Globals": {"Function": {"CodeUri": "s3://test-bucket/test-key"}},
            "Resources": {
                "FunResource": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs18.x"},
                }
            },
        }

        open_mock = mock.mock_open()
        yaml_parse_mock.return_value = template_dict

        # Patch the file open method to return template string
        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            template_exporter = Template(
                template_path, parent_dir, self.uploaders_mock, self.code_signer_mock, resources_to_export
            )
            exported_template = template_exporter.export()
            self.assertEqual(exported_template, template_dict)
            self.assertEqual(
                exported_template["Resources"]["FunResource"]["Properties"]["CodeUri"], "s3://test-bucket/test-key"
            )

    @patch("samcli.lib.package.artifact_exporter.yaml_parse")
    def test_template_global_export(self, yaml_parse_mock):
        parent_dir = os.path.sep
        template_dir = os.path.join(parent_dir, "foo", "bar")
        template_path = os.path.join(template_dir, "path")
        template_str = self.example_yaml_template()

        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "resource_type1"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance
        resource_type2_class = Mock()
        resource_type2_class.RESOURCE_TYPE = "resource_type2"
        resource_type2_class.ARTIFACT_TYPE = ZIP
        resource_type2_class.EXPORT_DESTINATION = Destination.S3
        resource_type2_instance = Mock()
        resource_type2_class.return_value = resource_type2_instance

        resources_to_export = {"resource_type1": resource_type1_class, "resource_type2": resource_type2_class}
        properties1 = {"foo": "bar", "Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": "foo.yaml"}}}
        properties2 = {"foo": "bar", "Fn::Transform": {"Name": "AWS::OtherTransform"}}
        properties_in_list = {"Fn::Transform": {"Name": "AWS::Include", "Parameters": {"Location": "bar.yaml"}}}
        template_dict = {
            "Resources": {
                "Resource1": {"Type": "resource_type1", "Properties": properties1},
                "Resource2": {"Type": "resource_type2", "Properties": properties2},
            },
            "List": ["foo", properties_in_list],
        }
        open_mock = mock.mock_open()
        include_transform_export_handler_mock = Mock()
        include_transform_export_handler_mock.return_value = {
            "Name": "AWS::Include",
            "Parameters": {"Location": "s3://foo"},
        }
        yaml_parse_mock.return_value = template_dict

        with patch("samcli.lib.package.artifact_exporter.open", open_mock(read_data=template_str)) as open_mock:
            with patch.dict(GLOBAL_EXPORT_DICT, {"Fn::Transform": include_transform_export_handler_mock}):
                template_exporter = Template(template_path, parent_dir, self.uploaders_mock, resources_to_export)
                exported_template = template_exporter._export_global_artifacts(template_exporter.template_dict)

                first_call_args, kwargs = include_transform_export_handler_mock.call_args_list[0]
                second_call_args, kwargs = include_transform_export_handler_mock.call_args_list[1]
                third_call_args, kwargs = include_transform_export_handler_mock.call_args_list[2]
                call_args = [first_call_args[0], second_call_args[0], third_call_args[0]]
                self.assertTrue({"Name": "AWS::Include", "Parameters": {"Location": "foo.yaml"}} in call_args)
                self.assertTrue({"Name": "AWS::OtherTransform"} in call_args)
                self.assertTrue({"Name": "AWS::Include", "Parameters": {"Location": "bar.yaml"}} in call_args)
                self.assertTrue(template_dir in first_call_args)
                self.assertTrue(template_dir in second_call_args)
                self.assertTrue(template_dir in third_call_args)
                self.assertEqual(include_transform_export_handler_mock.call_count, 3)
                # new s3 url is added to include location
                self.assertEqual(
                    exported_template["Resources"]["Resource1"]["Properties"]["Fn::Transform"],
                    {"Name": "AWS::Include", "Parameters": {"Location": "s3://foo"}},
                )
                self.assertEqual(
                    exported_template["List"][1]["Fn::Transform"],
                    {"Name": "AWS::Include", "Parameters": {"Location": "s3://foo"}},
                )

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_with_relative_file_path(self, is_local_file_mock):
        # exports transform
        parent_dir = os.path.abspath("someroot")
        self.s3_uploader_mock.upload_with_dedup.return_value = "s3://foo"
        is_local_file_mock.return_value = True
        abs_file_path = os.path.join(parent_dir, "foo.yaml")

        handler_output = include_transform_export_handler(
            {"Name": "AWS::Include", "Parameters": {"Location": "foo.yaml"}}, self.s3_uploader_mock, parent_dir
        )
        self.s3_uploader_mock.upload_with_dedup.assert_called_once_with(abs_file_path)
        is_local_file_mock.assert_called_with(abs_file_path)
        self.assertEqual(handler_output, {"Name": "AWS::Include", "Parameters": {"Location": "s3://foo"}})

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_with_absolute_file_path(self, is_local_file_mock):
        # exports transform
        parent_dir = os.path.abspath("someroot")
        self.s3_uploader_mock.upload_with_dedup.return_value = "s3://foo"
        is_local_file_mock.return_value = True
        abs_file_path = os.path.abspath(os.path.join("my", "file.yaml"))

        handler_output = include_transform_export_handler(
            {"Name": "AWS::Include", "Parameters": {"Location": abs_file_path}}, self.s3_uploader_mock, parent_dir
        )
        self.s3_uploader_mock.upload_with_dedup.assert_called_once_with(abs_file_path)
        is_local_file_mock.assert_called_with(abs_file_path)
        self.assertEqual(handler_output, {"Name": "AWS::Include", "Parameters": {"Location": "s3://foo"}})

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_with_s3_uri(self, is_local_file_mock):
        handler_output = include_transform_export_handler(
            {"Name": "AWS::Include", "Parameters": {"Location": "s3://bucket/foo.yaml"}},
            self.s3_uploader_mock,
            "parent_dir",
        )
        # Input is returned unmodified
        self.assertEqual(handler_output, {"Name": "AWS::Include", "Parameters": {"Location": "s3://bucket/foo.yaml"}})

        is_local_file_mock.assert_not_called()
        self.s3_uploader_mock.assert_not_called()

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_with_no_path(self, is_local_file_mock):
        handler_output = include_transform_export_handler(
            {"Name": "AWS::Include", "Parameters": {"Location": ""}}, self.s3_uploader_mock, "parent_dir"
        )
        # Input is returned unmodified
        self.assertEqual(handler_output, {"Name": "AWS::Include", "Parameters": {"Location": ""}})

        is_local_file_mock.assert_not_called()
        self.s3_uploader_mock.assert_not_called()

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_with_dict_value_for_location(self, is_local_file_mock):
        handler_output = include_transform_export_handler(
            {"Name": "AWS::Include", "Parameters": {"Location": {"Fn::Sub": "${S3Bucket}/file.txt"}}},
            self.s3_uploader_mock,
            "parent_dir",
        )
        # Input is returned unmodified
        self.assertEqual(
            handler_output, {"Name": "AWS::Include", "Parameters": {"Location": {"Fn::Sub": "${S3Bucket}/file.txt"}}}
        )

        is_local_file_mock.assert_not_called()
        self.s3_uploader_mock.assert_not_called()

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_non_local_file(self, is_local_file_mock):
        # returns unchanged template dict if transform not a local file, and not a S3 URI
        is_local_file_mock.return_value = False

        with self.assertRaises(exceptions.InvalidLocalPathError):
            include_transform_export_handler(
                {"Name": "AWS::Include", "Parameters": {"Location": "http://foo.yaml"}},
                self.s3_uploader_mock,
                "parent_dir",
            )
            is_local_file_mock.assert_called_with("http://foo.yaml")
            self.s3_uploader_mock.assert_not_called()

    @patch("samcli.lib.package.packageable_resources.is_local_file")
    def test_include_transform_export_handler_non_include_transform(self, is_local_file_mock):
        # ignores transform that is not aws::include
        handler_output = include_transform_export_handler(
            {"Name": "AWS::OtherTransform", "Parameters": {"Location": "foo.yaml"}}, self.s3_uploader_mock, "parent_dir"
        )
        self.s3_uploader_mock.upload_with_dedup.assert_not_called()
        self.assertEqual(handler_output, {"Name": "AWS::OtherTransform", "Parameters": {"Location": "foo.yaml"}})

    def test_template_export_path_be_folder(self):
        template_path = "/path/foo"
        # Set parent_dir to be a non-existent folder
        with self.assertRaises(ValueError):
            Template(template_path, "somefolder", self.uploaders_mock, self.code_signer_mock)
        # Set parent_dir to be a real folder, but just a relative path
        with self.make_temp_dir() as dirname:
            with self.assertRaises(ValueError):
                Template(template_path, os.path.relpath(dirname), self.uploaders_mock, self.code_signer_mock)

    def test_make_zip_keep_permissions_as_is(self):
        test_file_creator = FileCreator()
        test_file_creator.append_file(
            "index.js", "exports handler = (event, context, callback) => {callback(null, event);}"
        )

        dirname = test_file_creator.rootdir

        file_permissions = os.stat(test_file_creator.full_path("index.js")).st_mode
        dir_permissions = os.stat(test_file_creator.rootdir).st_mode

        expected_files = {"index.js"}

        random_name = "".join(random.choice(string.ascii_letters) for _ in range(10))
        outfile = os.path.join(tempfile.gettempdir(), random_name)

        zipfile_name = None
        try:
            zipfile_name = make_zip(outfile, dirname)

            test_zip_file = zipfile.ZipFile(zipfile_name, "r")
            with closing(test_zip_file) as zf:
                files_in_zip = set()
                external_attr_mask = 65535 << 16
                for info in zf.infolist():
                    files_in_zip.add(info.filename)
                    permission_bits = (info.external_attr & external_attr_mask) >> 16
                    if platform.system().lower() != "windows":
                        if info.is_dir():
                            self.assertEqual(permission_bits, dir_permissions)
                        else:
                            self.assertEqual(permission_bits, file_permissions)

                self.assertEqual(files_in_zip, expected_files)

        finally:
            if zipfile_name:
                os.remove(zipfile_name)
            test_file_creator.remove_all()

    def test_make_zip_keep_datetime_as_is(self):
        test_file_creator = FileCreator()
        test_file_creator.append_file(
            "index.js", "exports handler = (event, context, callback) => {callback(null, event);}"
        )

        dirname = test_file_creator.rootdir

        expected_files = {"index.js"}

        random_name = "".join(random.choice(string.ascii_letters) for _ in range(10))
        outfile = os.path.join(tempfile.gettempdir(), random_name)

        zipfile_name = None
        try:
            zipfile_name = make_zip(outfile, dirname)

            test_zip_file = zipfile.ZipFile(zipfile_name, "r")
            with closing(test_zip_file) as zf:
                files_in_zip = set()
                for info in zf.infolist():
                    files_in_zip.add(info.filename)
                    # This tests that we are not setting the datetime field of the info
                    # Currently we cannot set this field, for more information refer to
                    # https://github.com/aws/aws-sam-cli/pull/4781/files
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(files_in_zip, expected_files)

        finally:
            if zipfile_name:
                os.remove(zipfile_name)
            test_file_creator.remove_all()

    @patch("platform.system")
    def test_make_zip_windows(self, mock_system):
        mock_system.return_value = "Windows"
        # Redefining `make_zip` as is in local scope so that arguments passed to functools partial are re-loaded.
        windows_make_zip = functools.partial(
            make_zip_with_permissions,
            permission_mappers=[
                WindowsFilePermissionPermissionMapper(permissions=0o100755),
                WindowsDirPermissionPermissionMapper(permissions=0o100755),
                AdditiveFilePermissionPermissionMapper(permissions=0o100444),
                AdditiveDirPermissionPermissionMapper(permissions=0o100111),
            ],
        )

        test_file_creator = FileCreator()
        test_file_creator.append_file(
            "index.js", "exports handler = (event, context, callback) => {callback(null, event);}"
        )

        dirname = test_file_creator.rootdir

        expected_files = {"index.js"}

        random_name = "".join(random.choice(string.ascii_letters) for _ in range(10))
        outfile = os.path.join(tempfile.gettempdir(), random_name)

        zipfile_name = None
        try:
            zipfile_name = windows_make_zip(outfile, dirname)

            test_zip_file = zipfile.ZipFile(zipfile_name, "r")
            with closing(test_zip_file) as zf:
                files_in_zip = set()
                external_attr_mask = 65535 << 16
                for info in zf.infolist():
                    files_in_zip.add(info.filename)
                    permission_bits = (info.external_attr & external_attr_mask) >> 16
                    self.assertEqual(permission_bits, 0o100755)

                self.assertEqual(files_in_zip, expected_files)

        finally:
            if zipfile_name:
                os.remove(zipfile_name)
            test_file_creator.remove_all()

    def test_make_zip_lambda_resources(self):
        test_file_creator = FileCreator()
        test_file_creator.append_file(
            "index.js", "exports handler = (event, context, callback) => {callback(null, event);}"
        )

        dirname = test_file_creator.rootdir
        file_permissions = os.stat(test_file_creator.full_path("index.js")).st_mode
        dir_permissions = os.stat(test_file_creator.rootdir).st_mode

        expected_files = {"index.js"}

        random_name = "".join(random.choice(string.ascii_letters) for _ in range(10))
        outfile = os.path.join(tempfile.gettempdir(), random_name)

        zipfile_name = None
        try:
            zipfile_name = make_zip_with_lambda_permissions(outfile, dirname)

            test_zip_file = zipfile.ZipFile(zipfile_name, "r")
            with closing(test_zip_file) as zf:
                files_in_zip = set()
                external_attr_mask = 65535 << 16
                for info in zf.infolist():
                    files_in_zip.add(info.filename)
                    permission_bits = (info.external_attr & external_attr_mask) >> 16
                    if not platform.system().lower() == "windows":
                        if info.is_dir():
                            permission_difference = permission_bits ^ dir_permissions
                            self.assertTrue(permission_difference <= 0o100111)
                        else:
                            permission_difference = permission_bits ^ file_permissions
                            self.assertTrue(permission_difference <= 0o100444)
                    else:
                        self.assertEqual(permission_bits, 0o100755)

                self.assertEqual(files_in_zip, expected_files)

        finally:
            if zipfile_name:
                os.remove(zipfile_name)
            test_file_creator.remove_all()

    @patch("shutil.copyfile")
    @patch("tempfile.mkdtemp")
    def test_copy_to_temp_dir(self, mkdtemp_mock, copyfile_mock):
        temp_dir = "/tmp/foo/"
        filename = "test.js"
        mkdtemp_mock.return_value = temp_dir

        returned_dir = copy_to_temp_dir(filename)

        self.assertEqual(returned_dir, temp_dir)
        copyfile_mock.assert_called_once_with(filename, temp_dir + filename)

    @contextmanager
    def make_temp_dir(self):
        filename = tempfile.mkdtemp()
        try:
            yield filename
        finally:
            if filename:
                os.rmdir(filename)

    def example_yaml_template(self):
        return """
        AWSTemplateFormatVersion: '2010-09-09'
        Description: Simple CRUD webservice. State is stored in a SimpleTable (DynamoDB) resource.
        Resources:
        MyFunction:
          Type: AWS::Lambda::Function
          Properties:
            Code: ./handler
            Handler: index.get
            Role:
              Fn::GetAtt:
              - MyFunctionRole
              - Arn
            Timeout: 20
            Runtime: nodejs4.3
        """

    def test_template_delete(self):
        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "resource_type1"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance
        resource_type2_class = Mock()
        resource_type2_class.RESOURCE_TYPE = "resource_type2"
        resource_type2_class.ARTIFACT_TYPE = ZIP
        resource_type2_class.EXPORT_DESTINATION = Destination.S3
        resource_type2_instance = Mock()
        resource_type2_class.return_value = resource_type2_instance
        resource_type3_class = Mock()
        resource_type3_class.RESOURCE_TYPE = "resource_type3"
        resource_type3_class.ARTIFACT_TYPE = ZIP
        resource_type3_class.EXPORT_DESTINATION = Destination.S3
        resource_type3_instance = Mock()
        resource_type3_class.return_value = resource_type3_instance

        resources_to_export = [resource_type1_class, resource_type2_class]

        properties = {"foo": "bar"}
        template_dict = {
            "Resources": {
                "Resource1": {"Type": "resource_type1", "Properties": properties},
                "Resource2": {"Type": "resource_type2", "Properties": properties},
                "Resource3": {"Type": "some-other-type", "Properties": properties, "DeletionPolicy": "Retain"},
            }
        }
        template_str = json.dumps(template_dict, indent=4, ensure_ascii=False)

        template_exporter = Template(
            template_path=None,
            parent_dir=None,
            uploaders=self.uploaders_mock,
            code_signer=None,
            resources_to_export=resources_to_export,
            template_str=template_str,
        )

        template_exporter.delete(retain_resources=[])

        resource_type1_class.assert_called_once_with(self.uploaders_mock, None)
        resource_type1_instance.delete.assert_called_once_with("Resource1", mock.ANY)
        resource_type2_class.assert_called_once_with(self.uploaders_mock, None)
        resource_type2_instance.delete.assert_called_once_with("Resource2", mock.ANY)
        resource_type3_class.assert_not_called()
        resource_type3_instance.delete.assert_not_called()

    def test_get_ecr_repos(self):
        resources_to_export = [ECRResource]

        properties = {"RepositoryName": "test_repo"}
        template_dict = {
            "Resources": {
                "Resource1": {"Type": "AWS::ECR::Repository", "Properties": properties},
                "Resource2": {"Type": "resource_type1", "Properties": properties},
                "Resource3": {"Type": "AWS::ECR::Repository", "Properties": properties, "DeletionPolicy": "Retain"},
            }
        }

        template_str = json.dumps(template_dict, indent=4, ensure_ascii=False)

        template_exporter = Template(
            template_path=None,
            parent_dir=None,
            uploaders=self.uploaders_mock,
            code_signer=None,
            resources_to_export=resources_to_export,
            template_str=template_str,
        )

        repos = template_exporter.get_ecr_repos()
        self.assertEqual(repos, {"Resource1": {"Repository": "test_repo"}})

    def test_template_get_s3_info(self):
        resource_type1_class = Mock()
        resource_type1_class.RESOURCE_TYPE = "resource_type1"
        resource_type1_class.ARTIFACT_TYPE = ZIP
        resource_type1_class.PROPERTY_NAME = "CodeUri"
        resource_type1_class.EXPORT_DESTINATION = Destination.S3
        resource_type1_instance = Mock()
        resource_type1_class.return_value = resource_type1_instance
        resource_type1_instance.get_property_value = Mock()
        resource_type1_instance.get_property_value.return_value = {"Bucket": "bucket", "Key": "prefix/file"}

        resource_type2_class = Mock()
        resource_type2_class.RESOURCE_TYPE = "resource_type2"
        resource_type2_class.ARTIFACT_TYPE = ZIP
        resource_type2_class.EXPORT_DESTINATION = Destination.S3
        resource_type2_instance = Mock()
        resource_type2_class.return_value = resource_type2_instance

        resource_type3_class = Mock()
        resource_type3_class.RESOURCE_TYPE = "resource_type3"
        resource_type3_class.ARTIFACT_TYPE = IMAGE
        resource_type3_class.EXPORT_DESTINATION = Destination.ECR
        resource_type3_instance = Mock()
        resource_type3_class.return_value = resource_type3_instance

        resources_to_export = [resource_type3_class, resource_type2_class, resource_type1_class]

        properties = {"foo": "bar", "CodeUri": "s3://bucket/prefix/file"}
        template_dict = {
            "Resources": {
                "Resource1": {"Type": "resource_type1", "Properties": properties},
            }
        }
        template_str = json.dumps(template_dict, indent=4, ensure_ascii=False)

        template_exporter = Template(
            template_path=None,
            parent_dir=None,
            uploaders=self.uploaders_mock,
            code_signer=None,
            resources_to_export=resources_to_export,
            template_str=template_str,
        )

        s3_info = template_exporter.get_s3_info()
        self.assertEqual(s3_info, {"s3_bucket": "bucket", "s3_prefix": "prefix"})
        resource_type1_instance.get_property_value.assert_called_once_with(properties)

    @patch("samcli.lib.package.artifact_exporter.Template")
    def test_export_cloudformation_stack_with_language_extensions(self, TemplateMock):
        """
        When a child template uses Fn::ForEach, do_export should expand it,
        export the expanded template, then merge S3 URIs back.
        """
        from samcli.lib.cfn_language_extensions.sam_integration import LanguageExtensionResult

        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "NestedStack"
        property_name = stack_resource.PROPERTY_NAME
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"

        # The original child template has Fn::ForEach
        child_original = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::Serverless-2016-10-31", "AWS::LanguageExtensions"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                                "CodeUri": "./src",
                            },
                        }
                    },
                ]
            },
        }

        # The expanded template after language extensions processing
        child_expanded = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::Serverless-2016-10-31", "AWS::LanguageExtensions"],
            "Resources": {
                "UsersFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                        "CodeUri": "./src",
                    },
                },
                "OrdersFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                        "CodeUri": "./src",
                    },
                },
            },
        }

        # The exported template (after S3 upload) has S3 URIs
        child_exported = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::Serverless-2016-10-31", "AWS::LanguageExtensions"],
            "Resources": {
                "UsersFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                        "CodeUri": "s3://bucket/code.zip",
                    },
                },
                "OrdersFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                        "CodeUri": "s3://bucket/code.zip",
                    },
                },
            },
        }

        lang_ext_result = LanguageExtensionResult(
            expanded_template=child_expanded,
            original_template=child_original,
            dynamic_artifact_properties=[],
            had_language_extensions=True,
        )

        template_instance_mock = Mock()
        TemplateMock.return_value = template_instance_mock
        template_instance_mock.export.return_value = child_exported

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        handle = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False)
        try:
            handle.write("AWSTemplateFormatVersion: '2010-09-09'")
            handle.flush()
            template_path = handle.name
            handle.close()
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions",
                return_value=lang_ext_result,
            ):
                stack_resource.export(resource_id, resource_dict, parent_dir)

            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)

            # Template should have been called with the expanded template_str
            TemplateMock.assert_called_once()
            call_kwargs = TemplateMock.call_args
            self.assertIn("template_dict", call_kwargs.kwargs)

            template_instance_mock.export.assert_called_once_with()
            self.s3_uploader_mock.upload.assert_called_once_with(mock.ANY, mock.ANY)
        finally:
            os.remove(template_path)

    @patch("samcli.lib.package.artifact_exporter.Template")
    def test_export_cloudformation_stack_without_language_extensions(self, TemplateMock):
        """
        When a child template does NOT use language extensions,
        do_export should use the original flow (no expansion).
        """
        from samcli.lib.cfn_language_extensions.sam_integration import LanguageExtensionResult

        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "NestedStack"
        property_name = stack_resource.PROPERTY_NAME
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"
        exported_template_dict = {"Resources": {"MyFunc": {"Type": "AWS::Serverless::Function"}}}

        template_instance_mock = Mock()
        TemplateMock.return_value = template_instance_mock
        template_instance_mock.export.return_value = exported_template_dict

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        no_ext_result = LanguageExtensionResult(
            expanded_template={"Resources": {}},
            original_template={"Resources": {}},
            dynamic_artifact_properties=[],
            had_language_extensions=False,
        )

        handle = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False)
        try:
            handle.write("Resources: {}")
            handle.flush()
            template_path = handle.name
            handle.close()
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions",
                return_value=no_ext_result,
            ):
                stack_resource.export(resource_id, resource_dict, parent_dir)

            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)

            # In the no-extensions path, Template is called without template_str
            # (the second call, in the else branch)
            self.assertEqual(TemplateMock.call_count, 1)
            call_kwargs = TemplateMock.call_args
            self.assertNotIn("template_str", call_kwargs.kwargs)
        finally:
            os.remove(template_path)

    @patch("samcli.lib.package.artifact_exporter.Template")
    def test_export_cloudformation_stack_language_extensions_expansion_failure(self, TemplateMock):
        """
        When expand_language_extensions raises an exception,
        do_export should fall back to the original flow.
        """
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "NestedStack"
        property_name = stack_resource.PROPERTY_NAME
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"
        exported_template_dict = {"Resources": {"MyFunc": {"Type": "AWS::Serverless::Function"}}}

        template_instance_mock = Mock()
        TemplateMock.return_value = template_instance_mock
        template_instance_mock.export.return_value = exported_template_dict

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        handle = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False)
        try:
            handle.write("Resources: {}")
            handle.flush()
            template_path = handle.name
            handle.close()
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions",
                side_effect=InvalidSamDocumentException("expansion failed"),
            ):
                stack_resource.export(resource_id, resource_dict, parent_dir)

            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)
            # Falls back to non-extension flow
            self.assertEqual(TemplateMock.call_count, 1)
            call_kwargs = TemplateMock.call_args
            self.assertNotIn("template_str", call_kwargs.kwargs)
        finally:
            os.remove(template_path)

    @patch("samcli.lib.package.artifact_exporter.Template")
    def test_export_cloudformation_stack_unexpected_exception_falls_back(self, TemplateMock):
        """
        When expand_language_extensions raises an unexpected exception (not InvalidSamDocumentException),
        it should fall back gracefully to the non-extension flow (not abort the parent packaging).
        """
        stack_resource = CloudFormationStackResource(self.uploaders_mock, self.code_signer_mock)

        resource_id = "NestedStack"
        property_name = stack_resource.PROPERTY_NAME
        result_s3_url = "s3://hello/world"
        result_path_style_s3_url = "http://s3.amazonws.com/hello/world"
        exported_template_dict = {"Resources": {}}

        template_instance_mock = Mock()
        TemplateMock.return_value = template_instance_mock
        template_instance_mock.export.return_value = exported_template_dict

        self.s3_uploader_mock.upload.return_value = result_s3_url
        self.s3_uploader_mock.to_path_style_s3_url.return_value = result_path_style_s3_url

        handle = tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False)
        try:
            handle.write("Resources: {}")
            handle.flush()
            template_path = handle.name
            handle.close()
            resource_dict = {property_name: template_path}
            parent_dir = tempfile.gettempdir()

            with patch(
                "samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions",
                side_effect=TypeError("unexpected bug"),
            ):
                stack_resource.export(resource_id, resource_dict, parent_dir)

            # Should fall back to non-extension flow successfully
            self.assertEqual(resource_dict[property_name], result_path_style_s3_url)
        finally:
            os.remove(template_path)


class TestResolveNestedStackParameters(unittest.TestCase):
    """Unit tests for _resolve_nested_stack_parameters helper.

    This covers the fix for issue #1: child stack Fn::ForEach over a Ref to
    a parameter the parent passed down via Properties.Parameters. The helper
    is the seam that turns the parent's nested-stack Parameters property
    into a concrete parameter_values map usable by expand_language_extensions.
    """

    def test_literal_values_pass_through(self):
        from samcli.lib.package.artifact_exporter import _resolve_nested_stack_parameters

        resolved = _resolve_nested_stack_parameters(
            {"ServiceNames": "Users,Orders,Products"}, parent_parameter_values={}
        )
        self.assertEqual(resolved, {"ServiceNames": "Users,Orders,Products"})

    def test_ref_to_parent_parameter_resolves(self):
        from samcli.lib.package.artifact_exporter import _resolve_nested_stack_parameters

        resolved = _resolve_nested_stack_parameters(
            {"ServiceNames": {"Ref": "TopLevelServices"}},
            parent_parameter_values={"TopLevelServices": "Users,Orders"},
        )
        self.assertEqual(resolved, {"ServiceNames": "Users,Orders"})

    def test_unresolvable_getatt_is_dropped(self):
        from samcli.lib.package.artifact_exporter import _resolve_nested_stack_parameters

        resolved = _resolve_nested_stack_parameters(
            {"TopicArn": {"Fn::GetAtt": ["SomeResource", "Arn"]}}, parent_parameter_values={}
        )
        # Can't resolve at package time; the key is dropped so it doesn't
        # poison expand_language_extensions with a dict value.
        self.assertEqual(resolved, {})

    def test_empty_input(self):
        from samcli.lib.package.artifact_exporter import _resolve_nested_stack_parameters

        self.assertEqual(_resolve_nested_stack_parameters({}, {}), {})
        self.assertEqual(_resolve_nested_stack_parameters(None, {}), {})


class TestCloudFormationStackResourceChildExpansion(unittest.TestCase):
    """End-to-end test for threading parent params into child template expansion.

    Verifies that when CloudFormationStackResource.do_export is invoked with a
    parent_parameter_values attribute set, and the nested-stack resource has
    a Parameters property, those parameters reach the child-template
    language-extensions expansion (so Fn::ForEach over a child parameter
    resolves correctly).
    """

    def _make_stack_resource(self):
        uploaders_mock = Mock()
        uploaders_mock.get.return_value = Mock()
        uploaders_mock.get.return_value.upload.return_value = "s3://bucket/key"
        uploaders_mock.get.return_value.to_path_style_s3_url.return_value = "http://s3.amazonaws.com/bucket/key"
        code_signer_mock = Mock()
        code_signer_mock.should_sign_package.return_value = False
        return CloudFormationStackResource(uploaders_mock, code_signer_mock), uploaders_mock

    def test_child_template_receives_parent_parameters(self):
        stack_resource, _ = self._make_stack_resource()

        # Child template: Fn::ForEach driven by a child parameter.
        child_template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::LanguageExtensions",
            "Parameters": {"ServiceNames": {"Type": "CommaDelimitedList"}},
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    {"Ref": "ServiceNames"},
                    {"${Name}Topic": {"Type": "AWS::SNS::Topic", "Properties": {}}},
                ]
            },
        }

        tmpdir = tempfile.mkdtemp()
        try:
            child_path = os.path.join(tmpdir, "child.yaml")
            from samcli.yamlhelper import yaml_dump

            with open(child_path, "w", encoding="utf-8") as f:
                f.write(yaml_dump(child_template))

            # Parent-propagated values (what PackageContext._export would send)
            stack_resource.parent_parameter_values = {
                "AWS::Region": "us-east-1",
                "AWS::AccountId": "123456789012",
            }

            # Parent's nested-stack resource: Parameters literal list
            resource_dict = {
                "TemplateURL": child_path,
                "Parameters": {"ServiceNames": "Users,Orders,Products"},
            }

            with patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions") as expand_mock:
                # Short-circuit: make expand return a "no-LE" result so do_export
                # proceeds via the non-extension path (which doesn't upload since
                # we'll intercept the inner Template).
                expand_mock.return_value = Mock(had_language_extensions=False)
                with patch("samcli.lib.package.artifact_exporter.Template") as TemplateMock:
                    inner_template = Mock()
                    inner_template.export.return_value = {"Resources": {}}
                    TemplateMock.return_value = inner_template
                    stack_resource.do_export("ChildStack", resource_dict, tmpdir)

            # Verify the parameter_values threaded into expand_language_extensions
            # contains the nested-stack Parameters values.
            call_args = expand_mock.call_args[0]
            call_kwargs = expand_mock.call_args[1]
            passed_params = call_args[1] if len(call_args) > 1 else call_kwargs.get("parameter_values", {})
            self.assertEqual(passed_params.get("ServiceNames"), "Users,Orders,Products")
            # And still carries propagated parent/pseudo values:
            self.assertEqual(passed_params.get("AWS::Region"), "us-east-1")
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCloudFormationStackResourceExpansionErrorHandling(unittest.TestCase):
    """Error-path behavior for language-extensions expansion in do_export.

    Issue #2 in the review: the broad `except Exception` was downgrading
    SAM CLI bugs to warnings, silently masking defects. The new behavior:
    - InvalidSamDocumentException: warn (expected user-facing failure)
    - Other exceptions: log ERROR with traceback (bug, not user input)
    Both still fall back to the non-expanded path so the rest of sam
    package keeps going.
    """

    def _make_stack_resource(self):
        uploaders_mock = Mock()
        uploaders_mock.get.return_value = Mock()
        uploaders_mock.get.return_value.upload.return_value = "s3://bucket/key"
        uploaders_mock.get.return_value.to_path_style_s3_url.return_value = "http://s3.amazonaws.com/bucket/key"
        code_signer_mock = Mock()
        code_signer_mock.should_sign_package.return_value = False
        return CloudFormationStackResource(uploaders_mock, code_signer_mock)

    def _write_child(self, tmpdir):
        child = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::LanguageExtensions",
            "Resources": {"Dummy": {"Type": "AWS::SNS::Topic", "Properties": {}}},
        }
        from samcli.yamlhelper import yaml_dump

        path = os.path.join(tmpdir, "child.yaml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(yaml_dump(child))
        return path

    def test_invalid_sam_document_exception_logs_warning_and_falls_back(self):
        stack_resource = self._make_stack_resource()
        tmpdir = tempfile.mkdtemp()
        try:
            child_path = self._write_child(tmpdir)
            with (
                patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions") as expand_mock,
                patch("samcli.lib.package.artifact_exporter.Template") as TemplateMock,
                self.assertLogs("samcli.lib.package.artifact_exporter", level="WARNING") as log_ctx,
            ):
                expand_mock.side_effect = InvalidSamDocumentException("bad template")
                TemplateMock.return_value.export.return_value = {"Resources": {}}
                stack_resource.do_export("ChildStack", {"TemplateURL": child_path}, tmpdir)

            # Warning emitted (not error) and fallback path taken.
            self.assertTrue(any("Language extensions expansion failed" in m for m in log_ctx.output))
            TemplateMock.assert_called_once()  # non-extension fallback constructor
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_unexpected_exception_logs_error_and_falls_back(self):
        stack_resource = self._make_stack_resource()
        tmpdir = tempfile.mkdtemp()
        try:
            child_path = self._write_child(tmpdir)
            with (
                patch("samcli.lib.cfn_language_extensions.sam_integration.expand_language_extensions") as expand_mock,
                patch("samcli.lib.package.artifact_exporter.Template") as TemplateMock,
                self.assertLogs("samcli.lib.package.artifact_exporter", level="ERROR") as log_ctx,
            ):
                expand_mock.side_effect = AttributeError("unexpected bug")
                TemplateMock.return_value.export.return_value = {"Resources": {}}
                stack_resource.do_export("ChildStack", {"TemplateURL": child_path}, tmpdir)

            # ERROR-level log containing the bug-report pointer; fallback still taken.
            joined = "\n".join(log_ctx.output)
            self.assertIn("Internal error expanding language extensions", joined)
            self.assertIn("github.com/aws/aws-sam-cli/issues", joined)
            TemplateMock.assert_called_once()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)
