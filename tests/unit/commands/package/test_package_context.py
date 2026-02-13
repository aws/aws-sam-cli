"""Test sam package command"""

from unittest import TestCase
from unittest.mock import patch, MagicMock, Mock, call, ANY
from parameterized import parameterized
import tempfile


from samcli.commands.package.package_context import PackageContext
from samcli.commands.package.exceptions import PackageFailedError
from samcli.lib.cfn_language_extensions.sam_integration import (
    contains_loop_variable,
    detect_dynamic_artifact_properties,
)
from samcli.lib.package.artifact_exporter import Template
from samcli.lib.package.language_extensions_packaging import (
    merge_language_extensions_s3_uris,
    warn_parameter_based_collections,
    _update_resources_with_s3_uris,
    _update_foreach_with_s3_uris,
    _copy_artifact_uris_for_type,
    _copy_artifact_uris,
    _build_expanded_key,
    _generate_artifact_mappings,
    _validate_mapping_key_compatibility,
    _find_artifact_uri_for_resource,
    _apply_artifact_mappings_to_template,
    _replace_dynamic_artifact_with_findmap,
)
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION, AWS_SERVERLESS_FUNCTION


class TestPackageCommand(TestCase):
    def setUp(self):
        self.package_command_context = PackageContext(
            template_file="template-file",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository="image-repo",
            image_repositories=None,
            kms_key_id="kms-key-id",
            output_template_file=None,
            use_json=True,
            force_upload=True,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(SamLocalStackProvider, "get_stacks")
    @patch.object(Template, "export", MagicMock(sideeffect=OSError))
    @patch("boto3.client")
    def test_template_permissions_error(self, patched_boto, patched_get_stacks, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = Mock()
        mock_get_validated_client.return_value = docker_client_mock

        patched_get_stacks.return_value = Mock(), Mock()
        with self.assertRaises(PackageFailedError):
            with patch.object(self.package_command_context, "_warn_preview_runtime") as patched_warn_preview_runtime:
                self.package_command_context.run()

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_template_path_valid_with_output_template(self, patched_boto, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = Mock()
        mock_get_validated_client.return_value = docker_client_mock

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_output_template_file:
                package_command_context = PackageContext(
                    template_file=temp_template_file.name,
                    s3_bucket="s3-bucket",
                    s3_prefix="s3-prefix",
                    image_repository="image-repo",
                    image_repositories=None,
                    kms_key_id="kms-key-id",
                    output_template_file=temp_output_template_file.name,
                    use_json=True,
                    force_upload=True,
                    no_progressbar=False,
                    metadata={},
                    region="us-east-2",
                    profile=None,
                )
                package_command_context.run()

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_template_path_valid(self, patched_boto, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = Mock()
        mock_get_validated_client.return_value = docker_client_mock

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_template_path_valid_no_json(self, patched_boto, mock_get_validated_client):
        # Mock the docker client
        docker_client_mock = Mock()
        mock_get_validated_client.return_value = docker_client_mock

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=False,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch("samcli.commands.package.package_context.PackageContext._warn_preview_runtime")
    @patch("samcli.commands.package.package_context.get_resource_full_path_by_id")
    @patch.object(SamLocalStackProvider, "get_stacks")
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.Session")
    @patch("boto3.client")
    @patch("samcli.commands.package.package_context.get_boto_config_with_user_agent")
    def test_boto_clients_created_with_config(
        self,
        patched_get_config,
        patched_boto_client,
        patched_boto_session,
        patched_get_stacks,
        patched_get_resource_full_path_by_id,
        patched_warn_preview_runtime,
        mock_get_validated_client,
    ):
        # Mock the docker client
        docker_client_mock = Mock()
        mock_get_validated_client.return_value = docker_client_mock

        patched_get_stacks.return_value = Mock(), Mock()
        patched_get_resource_full_path_by_id.return_value = None
        with self.assertRaises(PackageFailedError):
            package_command_context = PackageContext(
                template_file="template_file",
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository=None,
                image_repositories={"RandomFunction": "ImageRepoUri"},
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region=None,
                profile=None,
            )
            package_command_context.run()

        patched_boto_client.assert_has_calls([call("s3", config=ANY)])
        patched_boto_client.assert_has_calls([call("ecr", config=ANY)])
        patched_boto_client.assert_has_calls([call("signer", config=ANY)])
        patched_warn_preview_runtime.assert_called_with(patched_get_stacks()[0])

        patched_get_config.assert_has_calls(
            [call(region_name=ANY, signature_version=ANY), call(region_name=ANY), call(region_name=ANY)]
        )

    @parameterized.expand(
        [
            (
                "preview_runtime",
                True,
                AWS_SERVERLESS_FUNCTION,
            ),
            (
                "ga_runtime",
                False,
                AWS_SERVERLESS_FUNCTION,
            ),
            (
                "preview_runtime",
                True,
                AWS_LAMBDA_FUNCTION,
            ),
            (
                "ga_runtime",
                False,
                AWS_LAMBDA_FUNCTION,
            ),
        ]
    )
    @patch("samcli.commands.package.package_context.PREVIEW_RUNTIMES", {"preview_runtime"})
    @patch("samcli.commands.package.package_context.click")
    def test_warn_preview_runtime(self, runtime, should_warn, function_type, patched_click):
        resources = {"MyFunction": {"Type": function_type, "Properties": {"Runtime": runtime}}}

        self.package_command_context._warn_preview_runtime([Mock(resources=resources)])

        if should_warn:
            patched_click.secho.assert_called_once()
        else:
            patched_click.secho.assert_not_called()


class TestPackageContextDockerLazyInitialization(TestCase):
    """Test cases for lazy Docker client initialization in PackageContext"""

    def setUp(self):
        self.package_command_context = PackageContext(
            template_file="template-file",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository="image-repo",
            image_repositories=None,
            kms_key_id="kms-key-id",
            output_template_file=None,
            use_json=True,
            force_upload=True,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_docker_client_not_validated_during_package_context_run(self, patched_boto, mock_get_validated_client):
        """Test that Docker client is not validated during PackageContext.run()"""
        mock_docker_client = Mock()
        mock_get_validated_client.return_value = mock_docker_client

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region="us-east-2",
                profile=None,
            )

            # Run the package context
            package_command_context.run()

            # Docker client validation should not have been called during run()
            mock_get_validated_client.assert_not_called()

            # ECR uploader should be created but Docker client not validated yet
            ecr_uploader = package_command_context.uploaders.ecr
            self.assertIsNone(ecr_uploader._validated_docker_client)

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_docker_client_validated_only_when_ecr_operations_performed(self, patched_boto, mock_get_validated_client):
        """Test that Docker client is validated only when ECR operations are performed"""
        mock_docker_client = Mock()
        mock_get_validated_client.return_value = mock_docker_client

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region="us-east-2",
                profile=None,
            )

            # Run the package context
            package_command_context.run()

            # Docker client validation should not have been called yet
            mock_get_validated_client.assert_not_called()

            # Access the docker_client property to trigger validation
            ecr_uploader = package_command_context.uploaders.ecr
            docker_client = ecr_uploader.docker_client

            # Now Docker client validation should have been called
            mock_get_validated_client.assert_called_once()
            self.assertEqual(docker_client, mock_docker_client)

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_ecr_uploader_created_with_none_docker_client(self, patched_boto, mock_get_validated_client):
        """Test that ECRUploader is created with None docker_client parameter"""
        mock_docker_client = Mock()
        mock_get_validated_client.return_value = mock_docker_client

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region="us-east-2",
                profile=None,
            )

            # Run the package context
            package_command_context.run()

            # Verify ECRUploader was created with None docker_client parameter
            ecr_uploader = package_command_context.uploaders.ecr
            self.assertIsNone(ecr_uploader._docker_client_param)
            self.assertIsNone(ecr_uploader._validated_docker_client)

    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_multiple_docker_client_accesses_only_validate_once(self, patched_boto, mock_get_validated_client):
        """Test that multiple accesses to docker_client only validate once"""
        mock_docker_client = Mock()
        mock_get_validated_client.return_value = mock_docker_client

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository="image-repo",
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region="us-east-2",
                profile=None,
            )

            # Run the package context
            package_command_context.run()

            ecr_uploader = package_command_context.uploaders.ecr

            # Access docker_client multiple times
            docker_client1 = ecr_uploader.docker_client
            docker_client2 = ecr_uploader.docker_client
            docker_client3 = ecr_uploader.docker_client

            # Docker client validation should only be called once
            mock_get_validated_client.assert_called_once()
            self.assertEqual(docker_client1, docker_client2)
            self.assertEqual(docker_client2, docker_client3)
            self.assertEqual(docker_client1, mock_docker_client)

    @patch("samcli.commands.package.package_context.sync_ecr_stack")
    @patch("samcli.lib.package.ecr_uploader.get_validated_container_client")
    @patch.object(ResourceMetadataNormalizer, "normalize", MagicMock())
    @patch.object(Template, "export", MagicMock(return_value={}))
    @patch("boto3.client")
    def test_package_with_resolve_image_repos(self, patched_boto, mock_get_validated_client, mock_sync_ecr_stack):
        # Mock the docker client
        docker_client_mock = Mock()
        mock_get_validated_client.return_value = docker_client_mock

        # Mock sync_ecr_stack to return image repositories
        expected_repos = {"Function1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/repo1"}
        mock_sync_ecr_stack.return_value = expected_repos

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as temp_template_file:
            package_command_context = PackageContext(
                template_file=temp_template_file.name,
                s3_bucket="s3-bucket",
                s3_prefix="s3-prefix",
                image_repository=None,
                image_repositories=None,
                kms_key_id="kms-key-id",
                output_template_file=None,
                use_json=True,
                force_upload=True,
                no_progressbar=False,
                metadata={},
                region="us-east-1",
                profile=None,
                resolve_image_repos=True,
            )
            package_command_context.run()

            # Verify sync_ecr_stack was called with correct arguments
            # This proves the resolve_image_repos code path was executed
            mock_sync_ecr_stack.assert_called_once()
            call_args = mock_sync_ecr_stack.call_args
            # Check that template file was passed
            self.assertEqual(call_args[0][0], temp_template_file.name)
            # Check that s3_bucket was passed
            self.assertEqual(call_args[0][3], "s3-bucket")


class TestPackageContextLanguageExtensions(TestCase):
    """Test cases for language extensions support in PackageContext"""

    def test_check_using_language_extension_string_transform(self):
        """Test detection of language extensions as a string transform"""
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        template = {"Transform": "AWS::LanguageExtensions"}
        self.assertTrue(check_using_language_extension(template))

    def test_check_using_language_extension_list_transform(self):
        """Test detection of language extensions in a list of transforms"""
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        template = {"Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"]}
        self.assertTrue(check_using_language_extension(template))

    def test_check_using_language_extension_no_transform(self):
        """Test that templates without language extensions return False"""
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        template = {"Transform": "AWS::Serverless-2016-10-31"}
        self.assertFalse(check_using_language_extension(template))

    def test_check_using_language_extension_none_template(self):
        """Test that None template returns False"""
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        self.assertFalse(check_using_language_extension(None))

    def test_check_using_language_extension_empty_template(self):
        """Test that empty template returns False"""
        from samcli.lib.cfn_language_extensions.sam_integration import check_using_language_extension

        self.assertFalse(check_using_language_extension({}))

    def test_update_original_template_with_s3_uris_preserves_foreach(self):
        """Test that Fn::ForEach structure is preserved when updating S3 URIs"""
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./src",
                                "Handler": "${Name}.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "Alpha.handler",
                        "Runtime": "python3.9",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "Beta.handler",
                        "Runtime": "python3.9",
                    },
                },
            },
        }

        result = merge_language_extensions_s3_uris(original_template, exported_template)

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Functions", result["Resources"])

        # Verify S3 URI is updated in the Fn::ForEach body
        foreach_body = result["Resources"]["Fn::ForEach::Functions"][2]
        self.assertEqual(
            foreach_body["${Name}Function"]["Properties"]["CodeUri"],
            "s3://bucket/abc123.zip",
        )

        # Verify other properties are preserved
        self.assertEqual(
            foreach_body["${Name}Function"]["Properties"]["Handler"],
            "${Name}.handler",
        )

    def test_update_original_template_with_s3_uris_regular_resources(self):
        """Test that regular resources (non-ForEach) are also updated correctly"""
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src",
                        "Handler": "app.handler",
                        "Runtime": "python3.9",
                    },
                }
            },
        }

        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/xyz789.zip",
                        "Handler": "app.handler",
                        "Runtime": "python3.9",
                    },
                }
            },
        }

        result = merge_language_extensions_s3_uris(original_template, exported_template)

        # Verify S3 URI is updated
        self.assertEqual(
            result["Resources"]["MyFunction"]["Properties"]["CodeUri"],
            "s3://bucket/xyz789.zip",
        )

    def test_copy_artifact_uris_for_type_serverless_function(self):
        """Test copying artifact URIs for AWS::Serverless::Function"""
        original_props = {"CodeUri": "./src", "Handler": "app.handler"}
        exported_props = {"CodeUri": "s3://bucket/code.zip", "Handler": "app.handler"}

        result = _copy_artifact_uris_for_type(original_props, exported_props, "AWS::Serverless::Function")

        self.assertTrue(result)
        self.assertEqual(original_props["CodeUri"], "s3://bucket/code.zip")

    def test_copy_artifact_uris_for_type_lambda_function(self):
        """Test copying artifact URIs for AWS::Lambda::Function"""
        original_props = {"Code": "./src", "Handler": "app.handler"}
        exported_props = {
            "Code": {"S3Bucket": "bucket", "S3Key": "code.zip"},
            "Handler": "app.handler",
        }

        result = _copy_artifact_uris_for_type(original_props, exported_props, "AWS::Lambda::Function")

        self.assertTrue(result)
        self.assertEqual(original_props["Code"], {"S3Bucket": "bucket", "S3Key": "code.zip"})

    def test_copy_artifact_uris_for_type_serverless_layer(self):
        """Test copying artifact URIs for AWS::Serverless::LayerVersion"""
        original_props = {"ContentUri": "./layer"}
        exported_props = {"ContentUri": "s3://bucket/layer.zip"}

        result = _copy_artifact_uris_for_type(original_props, exported_props, "AWS::Serverless::LayerVersion")

        self.assertTrue(result)
        self.assertEqual(original_props["ContentUri"], "s3://bucket/layer.zip")

    def test_copy_artifact_uris_for_type_serverless_api(self):
        """Test copying artifact URIs for AWS::Serverless::Api"""
        original_props = {"DefinitionUri": "./api.yaml"}
        exported_props = {"DefinitionUri": "s3://bucket/api.yaml"}

        result = _copy_artifact_uris_for_type(original_props, exported_props, "AWS::Serverless::Api")

        self.assertTrue(result)
        self.assertEqual(original_props["DefinitionUri"], "s3://bucket/api.yaml")

    def test_copy_artifact_uris_for_type_unknown_type(self):
        """Test that unknown resource types return False"""
        original_props = {"SomeProperty": "value"}
        exported_props = {"SomeProperty": "s3://bucket/value"}

        result = _copy_artifact_uris_for_type(original_props, exported_props, "AWS::Unknown::Resource")

        self.assertFalse(result)

    def test_update_foreach_with_s3_uris_multiple_resource_types(self):
        """Test updating Fn::ForEach with multiple resource types"""
        foreach_value = [
            "Name",
            ["Alpha", "Beta"],
            {
                "${Name}Function": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src",
                        "Handler": "${Name}.handler",
                    },
                },
                "${Name}Layer": {
                    "Type": "AWS::Serverless::LayerVersion",
                    "Properties": {
                        "ContentUri": "./layer",
                    },
                },
            },
        ]

        exported_resources = {
            "AlphaFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/func.zip",
                    "Handler": "Alpha.handler",
                },
            },
            "BetaFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/func.zip",
                    "Handler": "Beta.handler",
                },
            },
            "AlphaLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "ContentUri": "s3://bucket/layer.zip",
                },
            },
            "BetaLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "ContentUri": "s3://bucket/layer.zip",
                },
            },
        }

        _update_foreach_with_s3_uris("Fn::ForEach::Resources", foreach_value, exported_resources)

        # Verify both resource types have updated S3 URIs
        body = foreach_value[2]
        self.assertEqual(body["${Name}Function"]["Properties"]["CodeUri"], "s3://bucket/func.zip")
        self.assertEqual(body["${Name}Layer"]["Properties"]["ContentUri"], "s3://bucket/layer.zip")

    def test_update_foreach_with_s3_uris_invalid_foreach_structure(self):
        """Test that invalid Fn::ForEach structures are handled gracefully"""
        # Test with invalid structure (not a list)
        _update_foreach_with_s3_uris("Fn::ForEach::Test", "invalid", {})

        # Test with list that's too short
        _update_foreach_with_s3_uris("Fn::ForEach::Test", ["Name", ["Alpha"]], {})

        # Test with non-dict body
        _update_foreach_with_s3_uris("Fn::ForEach::Test", ["Name", ["Alpha"], "invalid"], {})

        # No exceptions should be raised

    def test_replace_dynamic_artifact_with_findmap_basic(self):
        """Test basic replacement of dynamic artifact property with Fn::FindInMap"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Services": [
                "Name",
                ["Users", "Orders", "Products"],
                {
                    "${Name}Service": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./services/${Name}",
                            "Handler": "index.handler",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["Users", "Orders", "Products"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        result = _replace_dynamic_artifact_with_findmap(resources, prop)

        self.assertTrue(result)

        # Verify the property was replaced with Fn::FindInMap
        body = resources["Fn::ForEach::Services"][2]
        code_uri = body["${Name}Service"]["Properties"]["CodeUri"]
        self.assertIsInstance(code_uri, dict)
        self.assertIn("Fn::FindInMap", code_uri)
        self.assertEqual(code_uri["Fn::FindInMap"], ["SAMCodeUriServices", {"Ref": "Name"}, "CodeUri"])

    def test_replace_dynamic_artifact_with_findmap_preserves_foreach_structure(self):
        """Test that Fn::ForEach structure is preserved after replacement"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Functions": [
                "FuncName",
                ["Alpha", "Beta"],
                {
                    "${FuncName}Function": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./${FuncName}",
                            "Handler": "${FuncName}.handler",
                            "Runtime": "python3.9",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Functions",
            loop_name="Functions",
            loop_variable="FuncName",
            collection=["Alpha", "Beta"],
            resource_key="${FuncName}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${FuncName}",
        )

        _replace_dynamic_artifact_with_findmap(resources, prop)

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Functions", resources)
        foreach_value = resources["Fn::ForEach::Functions"]
        self.assertIsInstance(foreach_value, list)
        self.assertEqual(len(foreach_value), 3)
        self.assertEqual(foreach_value[0], "FuncName")
        self.assertEqual(foreach_value[1], ["Alpha", "Beta"])

        # Verify other properties are preserved
        body = foreach_value[2]
        self.assertEqual(body["${FuncName}Function"]["Properties"]["Handler"], "${FuncName}.handler")
        self.assertEqual(body["${FuncName}Function"]["Properties"]["Runtime"], "python3.9")

    def test_replace_dynamic_artifact_with_findmap_invalid_foreach_key(self):
        """Test that invalid Fn::ForEach key returns False"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {}  # Empty resources - foreach_key won't be found

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::NonExistent",
            loop_name="NonExistent",
            loop_variable="Name",
            collection=["A", "B"],
            resource_key="${Name}Resource",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Name}",
        )

        result = _replace_dynamic_artifact_with_findmap(resources, prop)

        self.assertFalse(result)

    def test_replace_dynamic_artifact_with_findmap_invalid_foreach_structure(self):
        """Test that invalid Fn::ForEach structure returns False"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        # Test with invalid structure (not a list)
        resources = {"Fn::ForEach::Test": "invalid"}

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Test",
            loop_name="Test",
            loop_variable="Name",
            collection=["A", "B"],
            resource_key="${Name}Resource",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Name}",
        )

        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertFalse(result)

        # Test with list that's too short
        resources = {"Fn::ForEach::Test": ["Name", ["A"]]}
        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertFalse(result)

    def test_replace_dynamic_artifact_with_findmap_missing_resource_key(self):
        """Test that missing resource key in body returns False"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Test": [
                "Name",
                ["A", "B"],
                {
                    "${Name}OtherResource": {  # Different resource key
                        "Type": "AWS::Serverless::Function",
                        "Properties": {"CodeUri": "./src"},
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Test",
            loop_name="Test",
            loop_variable="Name",
            collection=["A", "B"],
            resource_key="${Name}Resource",  # This key doesn't exist in body
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Name}",
        )

        result = _replace_dynamic_artifact_with_findmap(resources, prop)
        self.assertFalse(result)

    def test_replace_dynamic_artifact_with_findmap_content_uri(self):
        """Test replacement for ContentUri property (LayerVersion)"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Layers": [
                "LayerName",
                ["Common", "Utils"],
                {
                    "${LayerName}Layer": {
                        "Type": "AWS::Serverless::LayerVersion",
                        "Properties": {
                            "ContentUri": "./layers/${LayerName}",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Layers",
            loop_name="Layers",
            loop_variable="LayerName",
            collection=["Common", "Utils"],
            resource_key="${LayerName}Layer",
            resource_type="AWS::Serverless::LayerVersion",
            property_name="ContentUri",
            property_value="./layers/${LayerName}",
        )

        result = _replace_dynamic_artifact_with_findmap(resources, prop)

        self.assertTrue(result)

        # Verify the property was replaced with Fn::FindInMap
        body = resources["Fn::ForEach::Layers"][2]
        content_uri = body["${LayerName}Layer"]["Properties"]["ContentUri"]
        self.assertIsInstance(content_uri, dict)
        self.assertIn("Fn::FindInMap", content_uri)
        self.assertEqual(content_uri["Fn::FindInMap"], ["SAMContentUriLayers", {"Ref": "LayerName"}, "ContentUri"])

    def test_apply_artifact_mappings_to_template_integration(self):
        """Test full integration of _apply_artifact_mappings_to_template with _replace_dynamic_artifact_with_findmap"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        mappings = {
            "SAMCodeUriServices": {
                "Users": {"CodeUri": "s3://bucket/users-abc123.zip"},
                "Orders": {"CodeUri": "s3://bucket/orders-def456.zip"},
            }
        }

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
            )
        ]

        result = _apply_artifact_mappings_to_template(template, mappings, dynamic_properties)

        # Verify Mappings section was added
        self.assertIn("Mappings", result)
        self.assertIn("SAMCodeUriServices", result["Mappings"])
        self.assertEqual(result["Mappings"]["SAMCodeUriServices"]["Users"]["CodeUri"], "s3://bucket/users-abc123.zip")
        self.assertEqual(result["Mappings"]["SAMCodeUriServices"]["Orders"]["CodeUri"], "s3://bucket/orders-def456.zip")

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Services", result["Resources"])

        # Verify CodeUri was replaced with Fn::FindInMap
        body = result["Resources"]["Fn::ForEach::Services"][2]
        code_uri = body["${Name}Service"]["Properties"]["CodeUri"]
        self.assertEqual(code_uri, {"Fn::FindInMap": ["SAMCodeUriServices", {"Ref": "Name"}, "CodeUri"]})


class TestPackageContextMappingsIntegration(TestCase):
    """Test cases for the complete Mappings transformation integration in _export()"""

    def test_export_with_dynamic_artifact_properties_generates_mappings(self):
        """Test that module-level functions generate Mappings for dynamic artifact properties"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "UsersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/users-abc123.zip",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                },
                "OrdersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/orders-def456.zip",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                },
            },
        }

        # Detect dynamic properties
        dynamic_properties = detect_dynamic_artifact_properties(original_template)

        # Verify dynamic properties were detected
        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].property_name, "CodeUri")
        self.assertEqual(dynamic_properties[0].loop_variable, "Name")

        # Update original template with S3 URIs (skipping dynamic properties)
        output_template = merge_language_extensions_s3_uris(original_template, exported_template, dynamic_properties)

        # Generate Mappings
        exported_resources = exported_template.get("Resources", {})
        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Apply Mappings to template
        output_template = _apply_artifact_mappings_to_template(output_template, mappings, dynamic_properties)

        # Verify Mappings section was added
        self.assertIn("Mappings", output_template)
        self.assertIn("SAMCodeUriServices", output_template["Mappings"])

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Services", output_template["Resources"])

        # Verify CodeUri was replaced with Fn::FindInMap
        body = output_template["Resources"]["Fn::ForEach::Services"][2]
        code_uri = body["${Name}Service"]["Properties"]["CodeUri"]
        self.assertEqual(code_uri, {"Fn::FindInMap": ["SAMCodeUriServices", {"Ref": "Name"}, "CodeUri"]})

        # Verify other properties are preserved
        self.assertEqual(body["${Name}Service"]["Properties"]["Handler"], "index.handler")
        self.assertEqual(body["${Name}Service"]["Properties"]["Runtime"], "python3.9")

    def test_export_with_static_artifact_properties_no_mappings(self):
        """Test that module-level functions do not generate Mappings for static artifact properties"""

        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./src",  # Static - same for all
                                "Handler": "${Name}.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "Alpha.handler",
                        "Runtime": "python3.9",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "Beta.handler",
                        "Runtime": "python3.9",
                    },
                },
            },
        }

        # Detect dynamic properties - should be empty for static CodeUri
        dynamic_properties = detect_dynamic_artifact_properties(original_template)

        # Verify no dynamic properties were detected
        self.assertEqual(len(dynamic_properties), 0)

        # Update original template with S3 URIs
        output_template = merge_language_extensions_s3_uris(original_template, exported_template, dynamic_properties)

        # Verify no Mappings section was added (since no dynamic properties)
        self.assertNotIn("Mappings", output_template)

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Functions", output_template["Resources"])

        # Verify S3 URI is updated in the Fn::ForEach body
        body = output_template["Resources"]["Fn::ForEach::Functions"][2]
        self.assertEqual(body["${Name}Function"]["Properties"]["CodeUri"], "s3://bucket/abc123.zip")

        # Verify other properties are preserved
        self.assertEqual(body["${Name}Function"]["Properties"]["Handler"], "${Name}.handler")

    def test_export_preserves_foreach_structure_with_multiple_dynamic_properties(self):
        """Test that multiple dynamic properties in the same ForEach are handled correctly"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        },
                        "${Name}Layer": {
                            "Type": "AWS::Serverless::LayerVersion",
                            "Properties": {
                                "ContentUri": "./layers/${Name}",
                            },
                        },
                    },
                ]
            },
        }

        # Detect dynamic properties
        dynamic_properties = detect_dynamic_artifact_properties(original_template)

        # Verify both dynamic properties were detected
        self.assertEqual(len(dynamic_properties), 2)
        property_names = {p.property_name for p in dynamic_properties}
        self.assertIn("CodeUri", property_names)
        self.assertIn("ContentUri", property_names)

    def test_generate_artifact_mappings_creates_correct_structure(self):
        """Test that _generate_artifact_mappings creates the correct Mappings structure"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders", "Products"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
            )
        ]

        exported_resources = {
            "UsersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/users-abc123.zip",
                    "Handler": "index.handler",
                },
            },
            "OrdersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/orders-def456.zip",
                    "Handler": "index.handler",
                },
            },
            "ProductsService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/products-ghi789.zip",
                    "Handler": "index.handler",
                },
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify Mappings structure
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertEqual(len(mappings["SAMCodeUriServices"]), 3)

        # Verify each collection value has a mapping entry
        self.assertIn("Users", mappings["SAMCodeUriServices"])
        self.assertIn("Orders", mappings["SAMCodeUriServices"])
        self.assertIn("Products", mappings["SAMCodeUriServices"])

        # Verify S3 URIs are correct
        self.assertEqual(mappings["SAMCodeUriServices"]["Users"]["CodeUri"], "s3://bucket/users-abc123.zip")
        self.assertEqual(mappings["SAMCodeUriServices"]["Orders"]["CodeUri"], "s3://bucket/orders-def456.zip")
        self.assertEqual(mappings["SAMCodeUriServices"]["Products"]["CodeUri"], "s3://bucket/products-ghi789.zip")

    def test_update_original_template_skips_dynamic_properties(self):
        """Test that merge_language_extensions_s3_uris skips dynamic properties"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",  # Dynamic - should be skipped
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "UsersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/users-abc123.zip",
                        "Handler": "index.handler",
                    },
                },
                "OrdersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/orders-def456.zip",
                        "Handler": "index.handler",
                    },
                },
            },
        }

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
            )
        ]

        result = merge_language_extensions_s3_uris(original_template, exported_template, dynamic_properties)

        # Verify the dynamic CodeUri property was NOT updated (still has original value)
        body = result["Resources"]["Fn::ForEach::Services"][2]
        self.assertEqual(body["${Name}Service"]["Properties"]["CodeUri"], "./services/${Name}")

    def test_detect_dynamic_artifact_properties_with_fn_sub(self):
        """Test detection of dynamic properties using Fn::Sub"""
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": {"Fn::Sub": "./services/${Name}"},
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # Verify dynamic property was detected even with Fn::Sub
        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].property_name, "CodeUri")

    def test_detect_dynamic_artifact_properties_with_parameter_collection(self):
        """Test detection of dynamic properties with parameter-based collection"""
        parameter_overrides = {"ServiceNames": "Users,Orders,Products"}

        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "ServiceNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Users,Orders",
                }
            },
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    {"Ref": "ServiceNames"},
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template, parameter_overrides)

        # Verify dynamic property was detected
        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].property_name, "CodeUri")

        # Verify collection was resolved from parameter_overrides
        self.assertEqual(dynamic_properties[0].collection, ["Users", "Orders", "Products"])

    def test_contains_loop_variable_nested_structures(self):
        """Test contains_loop_variable with nested structures"""
        # Test simple string
        self.assertTrue(contains_loop_variable("./src/${Name}", "Name"))
        self.assertFalse(contains_loop_variable("./src", "Name"))

        # Test Fn::Sub string
        self.assertTrue(contains_loop_variable({"Fn::Sub": "./src/${Name}"}, "Name"))
        self.assertFalse(contains_loop_variable({"Fn::Sub": "./src"}, "Name"))

        # Test Fn::Sub list format
        self.assertTrue(contains_loop_variable({"Fn::Sub": ["./src/${Name}", {}]}, "Name"))

        # Test nested dict
        self.assertTrue(contains_loop_variable({"key": {"nested": "./src/${Name}"}}, "Name"))

        # Test list
        self.assertTrue(contains_loop_variable(["./src/${Name}", "other"], "Name"))

    def test_substitute_loop_variable(self):
        """Test substitute_loop_variable correctly substitutes values"""
        from samcli.lib.cfn_language_extensions.sam_integration import substitute_loop_variable

        # Test basic substitution
        result = substitute_loop_variable("${Name}Service", "Name", "Users")
        self.assertEqual(result, "UsersService")

        # Test multiple occurrences
        result = substitute_loop_variable("${Name}/${Name}", "Name", "Test")
        self.assertEqual(result, "Test/Test")

        # Test no substitution needed
        result = substitute_loop_variable("StaticValue", "Name", "Users")
        self.assertEqual(result, "StaticValue")

    def test_find_artifact_uri_for_resource(self):
        """Test _find_artifact_uri_for_resource finds correct artifact URIs for all formats"""
        exported_resources = {
            "UsersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/users-abc123.zip",
                    "Handler": "index.handler",
                },
            },
            "UsersLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "ContentUri": "s3://bucket/layer-xyz789.zip",
                },
            },
            "LambdaFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"S3Bucket": "bucket", "S3Key": "lambda-code.zip"},
                    "Handler": "index.handler",
                },
            },
            # Format 3: {Bucket, Key} dict format
            "StateMachine": {
                "Type": "AWS::Serverless::StateMachine",
                "Properties": {
                    "DefinitionUri": {"Bucket": "bucket", "Key": "statemachine-def.json"},
                },
            },
            "ApiGateway": {
                "Type": "AWS::ApiGateway::RestApi",
                "Properties": {
                    "BodyS3Location": {"Bucket": "bucket", "Key": "api-spec.yaml"},
                },
            },
            # Format 4: {ImageUri} dict format (ECR)
            "ContainerFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "ImageUri": {"ImageUri": "123456789.dkr.ecr.us-east-1.amazonaws.com/repo:tag"},
                    "PackageType": "Image",
                },
            },
        }

        # Test Format 1: String URI for Serverless Function CodeUri
        result = _find_artifact_uri_for_resource(
            exported_resources, "UsersService", "AWS::Serverless::Function", "CodeUri"
        )
        self.assertEqual(result, "s3://bucket/users-abc123.zip")

        # Test Format 1: String URI for LayerVersion ContentUri
        result = _find_artifact_uri_for_resource(
            exported_resources, "UsersLayer", "AWS::Serverless::LayerVersion", "ContentUri"
        )
        self.assertEqual(result, "s3://bucket/layer-xyz789.zip")

        # Test Format 2: {S3Bucket, S3Key} dict for Lambda Function Code
        result = _find_artifact_uri_for_resource(exported_resources, "LambdaFunction", "AWS::Lambda::Function", "Code")
        self.assertEqual(result, "s3://bucket/lambda-code.zip")

        # Test Format 3: {Bucket, Key} dict for StateMachine DefinitionUri
        result = _find_artifact_uri_for_resource(
            exported_resources, "StateMachine", "AWS::Serverless::StateMachine", "DefinitionUri"
        )
        self.assertEqual(result, "s3://bucket/statemachine-def.json")

        # Test Format 3: {Bucket, Key} dict for API Gateway BodyS3Location
        result = _find_artifact_uri_for_resource(
            exported_resources, "ApiGateway", "AWS::ApiGateway::RestApi", "BodyS3Location"
        )
        self.assertEqual(result, "s3://bucket/api-spec.yaml")

        # Test Format 4: {ImageUri} dict for ECR container images
        result = _find_artifact_uri_for_resource(
            exported_resources, "ContainerFunction", "AWS::Serverless::Function", "ImageUri"
        )
        self.assertEqual(result, "123456789.dkr.ecr.us-east-1.amazonaws.com/repo:tag")

        # Test resource not found
        result = _find_artifact_uri_for_resource(
            exported_resources, "NonExistent", "AWS::Serverless::Function", "CodeUri"
        )
        self.assertIsNone(result)

        # Test wrong resource type
        result = _find_artifact_uri_for_resource(exported_resources, "UsersService", "AWS::Lambda::Function", "Code")
        self.assertIsNone(result)


class TestDynamicArtifactPropertyDetection(TestCase):
    """
    Comprehensive unit tests for dynamic artifact property detection.

    **Validates: Requirements 15.11**

    These tests verify:
    1. Detection of loop variable in CodeUri
    2. Detection in nested Fn::Sub structures
    3. Static properties are NOT flagged as dynamic
    4. All packageable resource types are tested
    """

    # =========================================================================
    # Tests for loop variable detection in CodeUri
    # =========================================================================

    def test_detect_loop_variable_in_codeuri_simple_string(self):
        """Test detection of loop variable in simple string CodeUri"""
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]
        self.assertEqual(prop.property_name, "CodeUri")
        self.assertEqual(prop.loop_variable, "Name")
        self.assertEqual(prop.property_value, "./services/${Name}")
        self.assertEqual(prop.collection, ["Users", "Orders"])

    def test_detect_loop_variable_in_codeuri_with_prefix_and_suffix(self):
        """Test detection of loop variable in CodeUri with prefix and suffix"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FuncName",
                    ["Alpha", "Beta", "Gamma"],
                    {
                        "${FuncName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./src/functions/${FuncName}/code",
                                "Handler": "app.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]
        self.assertEqual(prop.property_name, "CodeUri")
        self.assertEqual(prop.loop_variable, "FuncName")
        self.assertEqual(prop.property_value, "./src/functions/${FuncName}/code")

    # =========================================================================
    # Tests for nested Fn::Sub structures
    # =========================================================================

    def test_detect_loop_variable_in_fn_sub_string(self):
        """Test detection of loop variable in Fn::Sub string format"""
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": {"Fn::Sub": "./services/${Name}"},
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]
        self.assertEqual(prop.property_name, "CodeUri")

    def test_detect_loop_variable_in_fn_sub_list_format(self):
        """Test detection of loop variable in Fn::Sub list format"""
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": {"Fn::Sub": ["./services/${Name}", {}]},
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]
        self.assertEqual(prop.property_name, "CodeUri")

    def test_detect_loop_variable_in_nested_fn_sub_with_variables(self):
        """Test detection of loop variable in Fn::Sub with variable substitutions"""
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": {"Fn::Sub": ["./services/${Name}/${Env}", {"Env": "prod"}]},
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]
        self.assertEqual(prop.property_name, "CodeUri")

    # =========================================================================
    # Tests for static properties NOT being flagged as dynamic
    # =========================================================================

    def test_static_codeuri_not_flagged_as_dynamic(self):
        """Test that static CodeUri is NOT flagged as dynamic"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./src",  # Static - no loop variable
                                "Handler": "${Name}.handler",  # Dynamic handler is OK
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # No dynamic artifact properties should be detected
        self.assertEqual(len(dynamic_properties), 0)

    def test_static_fn_sub_not_flagged_as_dynamic(self):
        """Test that Fn::Sub without loop variable is NOT flagged as dynamic"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": {"Fn::Sub": "./src/${AWS::Region}"},  # Uses pseudo-param, not loop var
                                "Handler": "${Name}.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # No dynamic artifact properties should be detected
        self.assertEqual(len(dynamic_properties), 0)

    def test_static_s3_uri_not_flagged_as_dynamic(self):
        """Test that S3 URI CodeUri is NOT flagged as dynamic"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "s3://my-bucket/code.zip",  # S3 URI - static
                                "Handler": "${Name}.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # No dynamic artifact properties should be detected
        self.assertEqual(len(dynamic_properties), 0)

    def test_mixed_static_and_dynamic_properties(self):
        """Test that only dynamic properties are flagged when mixed with static"""
        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",  # Dynamic
                                "Handler": "index.handler",
                            },
                        },
                        "${Name}Layer": {
                            "Type": "AWS::Serverless::LayerVersion",
                            "Properties": {
                                "ContentUri": "./common-layer",  # Static
                            },
                        },
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # Only the dynamic CodeUri should be detected
        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].property_name, "CodeUri")
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::Function")

    # =========================================================================
    # Tests for all packageable resource types
    # =========================================================================

    def test_detect_dynamic_property_aws_serverless_function_codeuri(self):
        """Test detection of dynamic CodeUri in AWS::Serverless::Function"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./functions/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::Function")
        self.assertEqual(dynamic_properties[0].property_name, "CodeUri")

    def test_detect_dynamic_property_aws_serverless_function_imageuri(self):
        """Test detection of dynamic ImageUri in AWS::Serverless::Function"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "ImageUri": "./images/${Name}",
                                "PackageType": "Image",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::Function")
        self.assertEqual(dynamic_properties[0].property_name, "ImageUri")

    def test_detect_dynamic_property_aws_lambda_function_code(self):
        """Test detection of dynamic Code in AWS::Lambda::Function"""
        template = {
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Lambda::Function",
                            "Properties": {
                                "Code": "./functions/${Name}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                                "Role": {"Fn::GetAtt": ["LambdaRole", "Arn"]},
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Lambda::Function")
        self.assertEqual(dynamic_properties[0].property_name, "Code")

    def test_detect_dynamic_property_aws_serverless_layerversion_contenturi(self):
        """Test detection of dynamic ContentUri in AWS::Serverless::LayerVersion"""
        template = {
            "Resources": {
                "Fn::ForEach::Layers": [
                    "Name",
                    ["Common", "Utils"],
                    {
                        "${Name}Layer": {
                            "Type": "AWS::Serverless::LayerVersion",
                            "Properties": {
                                "ContentUri": "./layers/${Name}",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::LayerVersion")
        self.assertEqual(dynamic_properties[0].property_name, "ContentUri")

    def test_detect_dynamic_property_aws_lambda_layerversion_content(self):
        """Test detection of dynamic Content in AWS::Lambda::LayerVersion"""
        template = {
            "Resources": {
                "Fn::ForEach::Layers": [
                    "Name",
                    ["Common", "Utils"],
                    {
                        "${Name}Layer": {
                            "Type": "AWS::Lambda::LayerVersion",
                            "Properties": {
                                "Content": "./layers/${Name}",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Lambda::LayerVersion")
        self.assertEqual(dynamic_properties[0].property_name, "Content")

    def test_detect_dynamic_property_aws_serverless_api_definitionuri(self):
        """Test detection of dynamic DefinitionUri in AWS::Serverless::Api"""
        template = {
            "Resources": {
                "Fn::ForEach::APIs": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Api": {
                            "Type": "AWS::Serverless::Api",
                            "Properties": {
                                "StageName": "prod",
                                "DefinitionUri": "./api/${Name}/openapi.yaml",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::Api")
        self.assertEqual(dynamic_properties[0].property_name, "DefinitionUri")

    def test_detect_dynamic_property_aws_serverless_httpapi_definitionuri(self):
        """Test detection of dynamic DefinitionUri in AWS::Serverless::HttpApi"""
        template = {
            "Resources": {
                "Fn::ForEach::APIs": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}HttpApi": {
                            "Type": "AWS::Serverless::HttpApi",
                            "Properties": {
                                "StageName": "prod",
                                "DefinitionUri": "./api/${Name}/openapi.yaml",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::HttpApi")
        self.assertEqual(dynamic_properties[0].property_name, "DefinitionUri")

    def test_detect_dynamic_property_aws_serverless_statemachine_definitionuri(self):
        """Test detection of dynamic DefinitionUri in AWS::Serverless::StateMachine"""
        template = {
            "Resources": {
                "Fn::ForEach::StateMachines": [
                    "Name",
                    ["Workflow1", "Workflow2"],
                    {
                        "${Name}StateMachine": {
                            "Type": "AWS::Serverless::StateMachine",
                            "Properties": {
                                "DefinitionUri": "./statemachines/${Name}/definition.asl.json",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::StateMachine")
        self.assertEqual(dynamic_properties[0].property_name, "DefinitionUri")

    def test_detect_dynamic_property_aws_serverless_graphqlapi_schemauri(self):
        """Test detection of dynamic SchemaUri in AWS::Serverless::GraphQLApi"""
        template = {
            "Resources": {
                "Fn::ForEach::GraphQLApis": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}GraphQLApi": {
                            "Type": "AWS::Serverless::GraphQLApi",
                            "Properties": {
                                "SchemaUri": "./graphql/${Name}/schema.graphql",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::GraphQLApi")
        self.assertEqual(dynamic_properties[0].property_name, "SchemaUri")

    def test_detect_dynamic_property_aws_serverless_graphqlapi_codeuri(self):
        """Test detection of dynamic CodeUri in AWS::Serverless::GraphQLApi"""
        template = {
            "Resources": {
                "Fn::ForEach::GraphQLApis": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}GraphQLApi": {
                            "Type": "AWS::Serverless::GraphQLApi",
                            "Properties": {
                                "CodeUri": "./graphql/${Name}/resolvers",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::Serverless::GraphQLApi")
        self.assertEqual(dynamic_properties[0].property_name, "CodeUri")

    def test_detect_dynamic_property_aws_apigateway_restapi_bodys3location(self):
        """Test detection of dynamic BodyS3Location in AWS::ApiGateway::RestApi"""
        template = {
            "Resources": {
                "Fn::ForEach::APIs": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}RestApi": {
                            "Type": "AWS::ApiGateway::RestApi",
                            "Properties": {
                                "BodyS3Location": "./api/${Name}/swagger.yaml",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::ApiGateway::RestApi")
        self.assertEqual(dynamic_properties[0].property_name, "BodyS3Location")

    def test_detect_dynamic_property_aws_apigatewayv2_api_bodys3location(self):
        """Test detection of dynamic BodyS3Location in AWS::ApiGatewayV2::Api"""
        template = {
            "Resources": {
                "Fn::ForEach::APIs": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}HttpApi": {
                            "Type": "AWS::ApiGatewayV2::Api",
                            "Properties": {
                                "BodyS3Location": "./api/${Name}/openapi.yaml",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::ApiGatewayV2::Api")
        self.assertEqual(dynamic_properties[0].property_name, "BodyS3Location")

    def test_detect_dynamic_property_aws_stepfunctions_statemachine_definitions3location(self):
        """Test detection of dynamic DefinitionS3Location in AWS::StepFunctions::StateMachine"""
        template = {
            "Resources": {
                "Fn::ForEach::StateMachines": [
                    "Name",
                    ["Workflow1", "Workflow2"],
                    {
                        "${Name}StateMachine": {
                            "Type": "AWS::StepFunctions::StateMachine",
                            "Properties": {
                                "DefinitionS3Location": "./statemachines/${Name}/definition.json",
                                "RoleArn": {"Fn::GetAtt": ["StepFunctionsRole", "Arn"]},
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 1)
        self.assertEqual(dynamic_properties[0].resource_type, "AWS::StepFunctions::StateMachine")
        self.assertEqual(dynamic_properties[0].property_name, "DefinitionS3Location")

    # =========================================================================
    # Tests for multiple artifact properties in same resource
    # =========================================================================

    def test_detect_multiple_dynamic_properties_in_same_resource(self):
        """Test detection of multiple dynamic properties in the same resource type"""
        template = {
            "Resources": {
                "Fn::ForEach::GraphQLApis": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}GraphQLApi": {
                            "Type": "AWS::Serverless::GraphQLApi",
                            "Properties": {
                                "SchemaUri": "./graphql/${Name}/schema.graphql",
                                "CodeUri": "./graphql/${Name}/resolvers",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # Both SchemaUri and CodeUri should be detected
        self.assertEqual(len(dynamic_properties), 2)
        property_names = {p.property_name for p in dynamic_properties}
        self.assertIn("SchemaUri", property_names)
        self.assertIn("CodeUri", property_names)

    # =========================================================================
    # Tests for edge cases
    # =========================================================================

    def test_no_dynamic_properties_for_non_packageable_resource(self):
        """Test that non-packageable resource types are not flagged"""
        template = {
            "Resources": {
                "Fn::ForEach::Tables": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Table": {
                            "Type": "AWS::DynamoDB::Table",
                            "Properties": {
                                "TableName": "${Name}Table",
                                "AttributeDefinitions": [{"AttributeName": "id", "AttributeType": "S"}],
                                "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # DynamoDB tables don't have packageable artifact properties
        self.assertEqual(len(dynamic_properties), 0)

    def test_no_dynamic_properties_when_no_foreach(self):
        """Test that templates without Fn::ForEach return no dynamic properties"""
        template = {
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src",
                        "Handler": "index.handler",
                    },
                }
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 0)

    def test_no_dynamic_properties_when_resources_is_empty(self):
        """Test that empty Resources section returns no dynamic properties"""
        template = {"Resources": {}}

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 0)

    def test_no_dynamic_properties_when_resources_is_missing(self):
        """Test that missing Resources section returns no dynamic properties"""
        template = {"AWSTemplateFormatVersion": "2010-09-09"}

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 0)

    def test_invalid_foreach_structure_returns_no_properties(self):
        """Test that invalid Fn::ForEach structure returns no dynamic properties"""
        # Invalid: Fn::ForEach value is not a list
        template = {
            "Resources": {"Fn::ForEach::Invalid": "not-a-list"},
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 0)

    def test_foreach_with_wrong_number_of_elements(self):
        """Test that Fn::ForEach with wrong number of elements returns no properties"""
        # Invalid: Fn::ForEach should have exactly 3 elements
        template = {
            "Resources": {"Fn::ForEach::Invalid": ["Name", ["Alpha", "Beta"]]},  # Missing body
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        self.assertEqual(len(dynamic_properties), 0)


class TestPackageContextExportIntegration(TestCase):
    """Test cases for the complete _export() method integration"""

    @patch("samcli.commands.package.package_context.Template")
    @patch("builtins.open", create=True)
    @patch("samcli.commands.package.package_context.yaml_parse")
    def test_export_with_language_extensions_and_dynamic_properties(
        self, mock_yaml_parse, mock_open, mock_template_class
    ):
        """Test _export() with language extensions and dynamic artifact properties"""
        package_context = PackageContext(
            template_file="template.yaml",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository=None,
            image_repositories=None,
            kms_key_id=None,
            output_template_file=None,
            use_json=False,
            force_upload=False,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )
        # Mock uploaders and code_signer which are set in run()
        package_context.uploaders = Mock()
        package_context.code_signer = Mock()

        # Mock the original template with dynamic CodeUri
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }
        mock_yaml_parse.return_value = original_template

        # Mock the exported template (after artifact upload)
        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "UsersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/users-abc123.zip",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                },
                "OrdersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/orders-def456.zip",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                },
            },
        }
        mock_template_instance = Mock()
        mock_template_instance.export.return_value = exported_template
        mock_template_class.return_value = mock_template_instance

        # Mock file open
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = ""

        # Call _export
        result = package_context._export("template.yaml", use_json=False)

        # Parse the result
        from samcli.yamlhelper import yaml_parse as real_yaml_parse

        output_template = real_yaml_parse(result)

        # Verify Mappings section was added
        self.assertIn("Mappings", output_template)
        self.assertIn("SAMCodeUriServices", output_template["Mappings"])

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Services", output_template["Resources"])

        # Verify CodeUri was replaced with Fn::FindInMap
        body = output_template["Resources"]["Fn::ForEach::Services"][2]
        code_uri = body["${Name}Service"]["Properties"]["CodeUri"]
        self.assertEqual(code_uri, {"Fn::FindInMap": ["SAMCodeUriServices", {"Ref": "Name"}, "CodeUri"]})

        # Verify S3 URIs are in the Mappings
        self.assertEqual(
            output_template["Mappings"]["SAMCodeUriServices"]["Users"]["CodeUri"], "s3://bucket/users-abc123.zip"
        )
        self.assertEqual(
            output_template["Mappings"]["SAMCodeUriServices"]["Orders"]["CodeUri"], "s3://bucket/orders-def456.zip"
        )

    @patch("samcli.commands.package.package_context.Template")
    @patch("builtins.open", create=True)
    @patch("samcli.commands.package.package_context.yaml_parse")
    def test_export_with_language_extensions_and_static_properties(
        self, mock_yaml_parse, mock_open, mock_template_class
    ):
        """Test _export() with language extensions and static artifact properties"""
        package_context = PackageContext(
            template_file="template.yaml",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository=None,
            image_repositories=None,
            kms_key_id=None,
            output_template_file=None,
            use_json=False,
            force_upload=False,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )
        # Mock uploaders and code_signer which are set in run()
        package_context.uploaders = Mock()
        package_context.code_signer = Mock()

        # Mock the original template with static CodeUri
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Functions": [
                    "Name",
                    ["Alpha", "Beta"],
                    {
                        "${Name}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./src",  # Static - same for all
                                "Handler": "${Name}.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }
        mock_yaml_parse.return_value = original_template

        # Mock the exported template (after artifact upload)
        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "AlphaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "Alpha.handler",
                        "Runtime": "python3.9",
                    },
                },
                "BetaFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "Beta.handler",
                        "Runtime": "python3.9",
                    },
                },
            },
        }
        mock_template_instance = Mock()
        mock_template_instance.export.return_value = exported_template
        mock_template_class.return_value = mock_template_instance

        # Mock file open
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = ""

        # Call _export
        result = package_context._export("template.yaml", use_json=False)

        # Parse the result
        from samcli.yamlhelper import yaml_parse as real_yaml_parse

        output_template = real_yaml_parse(result)

        # Verify no Mappings section was added (static properties don't need Mappings)
        self.assertNotIn("Mappings", output_template)

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Functions", output_template["Resources"])

        # Verify S3 URI is updated in the Fn::ForEach body
        body = output_template["Resources"]["Fn::ForEach::Functions"][2]
        self.assertEqual(body["${Name}Function"]["Properties"]["CodeUri"], "s3://bucket/abc123.zip")

        # Verify other properties are preserved
        self.assertEqual(body["${Name}Function"]["Properties"]["Handler"], "${Name}.handler")

    @patch("samcli.commands.package.package_context.Template")
    @patch("builtins.open", create=True)
    @patch("samcli.commands.package.package_context.yaml_parse")
    def test_export_without_language_extensions(self, mock_yaml_parse, mock_open, mock_template_class):
        """Test _export() without language extensions returns exported template as-is"""
        package_context = PackageContext(
            template_file="template.yaml",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository=None,
            image_repositories=None,
            kms_key_id=None,
            output_template_file=None,
            use_json=False,
            force_upload=False,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
        )
        # Mock uploaders and code_signer which are set in run()
        package_context.uploaders = Mock()
        package_context.code_signer = Mock()

        # Mock the original template without language extensions
        original_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "./src",
                        "Handler": "app.handler",
                        "Runtime": "python3.9",
                    },
                }
            },
        }
        mock_yaml_parse.return_value = original_template

        # Mock the exported template
        exported_template = {
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/abc123.zip",
                        "Handler": "app.handler",
                        "Runtime": "python3.9",
                    },
                }
            },
        }
        mock_template_instance = Mock()
        mock_template_instance.export.return_value = exported_template
        mock_template_class.return_value = mock_template_instance

        # Mock file open
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = ""

        # Call _export
        result = package_context._export("template.yaml", use_json=False)

        # Parse the result
        from samcli.yamlhelper import yaml_parse as real_yaml_parse

        output_template = real_yaml_parse(result)

        # Verify the exported template is returned as-is
        self.assertEqual(output_template, exported_template)


class TestPackageContextParameterBasedCollectionWarning(TestCase):
    """Test cases for warning when using parameter-based collections with dynamic artifact properties"""

    def test_detect_foreach_dynamic_properties_with_parameter_ref(self):
        """Test that parameter-based collections are detected correctly"""
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Parameters": {
                "ServiceNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Users,Orders",
                }
            },
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    {"Ref": "ServiceNames"},  # Parameter reference
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(
            template, parameter_values={"ServiceNames": "Users,Orders"}
        )

        # Verify dynamic property was detected
        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]

        # Verify parameter reference was detected
        self.assertTrue(prop.collection_is_parameter_ref)
        self.assertEqual(prop.collection_parameter_name, "ServiceNames")

    def test_detect_foreach_dynamic_properties_with_static_list(self):
        """Test that static list collections are not flagged as parameter references"""
        from samcli.lib.cfn_language_extensions.sam_integration import detect_dynamic_artifact_properties

        template = {
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],  # Static list
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(template)

        # Verify dynamic property was detected
        self.assertEqual(len(dynamic_properties), 1)
        prop = dynamic_properties[0]

        # Verify it's not flagged as parameter reference
        self.assertFalse(prop.collection_is_parameter_ref)
        self.assertIsNone(prop.collection_parameter_name)

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_warn_parameter_based_collections_emits_warning(self, mock_click):
        """Test that warning is emitted for parameter-based collections with dynamic properties"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
                collection_is_parameter_ref=True,
                collection_parameter_name="ServiceNames",
            )
        ]

        warn_parameter_based_collections(dynamic_properties)

        # Verify warning was emitted
        mock_click.secho.assert_called_once()
        call_args = mock_click.secho.call_args
        warning_msg = call_args[0][0]

        # Verify warning message content
        self.assertIn("Fn::ForEach 'Services'", warning_msg)
        self.assertIn("dynamic CodeUri", warning_msg)
        self.assertIn("!Ref ServiceNames", warning_msg)
        self.assertIn("Collection values are fixed at package time", warning_msg)
        self.assertIn("re-package", warning_msg)

        # Verify warning color
        self.assertEqual(call_args[1]["fg"], "yellow")

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_warn_parameter_based_collections_no_warning_for_static_list(self, mock_click):
        """Test that no warning is emitted for static list collections"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
                collection_is_parameter_ref=False,  # Static list
                collection_parameter_name=None,
            )
        ]

        warn_parameter_based_collections(dynamic_properties)

        # Verify no warning was emitted
        mock_click.secho.assert_not_called()

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_warn_parameter_based_collections_single_warning_per_loop(self, mock_click):
        """Test that only one warning is emitted per ForEach loop even with multiple dynamic properties"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        # Two dynamic properties from the same ForEach loop
        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
                collection_is_parameter_ref=True,
                collection_parameter_name="ServiceNames",
            ),
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",  # Same loop
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Layer",
                resource_type="AWS::Serverless::LayerVersion",
                property_name="ContentUri",
                property_value="./layers/${Name}",
                collection_is_parameter_ref=True,
                collection_parameter_name="ServiceNames",
            ),
        ]

        warn_parameter_based_collections(dynamic_properties)

        # Verify only one warning was emitted (not two)
        self.assertEqual(mock_click.secho.call_count, 1)

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_warn_parameter_based_collections_multiple_loops(self, mock_click):
        """Test that warnings are emitted for each ForEach loop with parameter-based collection"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        # Two dynamic properties from different ForEach loops
        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
                collection_is_parameter_ref=True,
                collection_parameter_name="ServiceNames",
            ),
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Layers",  # Different loop
                loop_name="Layers",
                loop_variable="LayerName",
                collection=["Common", "Utils"],
                resource_key="${LayerName}Layer",
                resource_type="AWS::Serverless::LayerVersion",
                property_name="ContentUri",
                property_value="./layers/${LayerName}",
                collection_is_parameter_ref=True,
                collection_parameter_name="LayerNames",
            ),
        ]

        warn_parameter_based_collections(dynamic_properties)

        # Verify two warnings were emitted (one per loop)
        self.assertEqual(mock_click.secho.call_count, 2)

    @patch("samcli.commands.package.package_context.Template")
    @patch("builtins.open", create=True)
    @patch("samcli.commands.package.package_context.yaml_parse")
    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_export_emits_warning_for_parameter_based_collection(
        self, mock_click, mock_yaml_parse, mock_open, mock_template_class
    ):
        """Test that _export() emits warning for parameter-based collections with dynamic properties"""
        package_context = PackageContext(
            template_file="template.yaml",
            s3_bucket="s3-bucket",
            s3_prefix="s3-prefix",
            image_repository=None,
            image_repositories=None,
            kms_key_id=None,
            output_template_file=None,
            use_json=False,
            force_upload=False,
            no_progressbar=False,
            metadata={},
            region=None,
            profile=None,
            parameter_overrides={"ServiceNames": "Users,Orders"},
        )
        # Mock uploaders and code_signer which are set in run()
        package_context.uploaders = Mock()
        package_context.code_signer = Mock()

        # Mock the original template with parameter-based collection
        original_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "ServiceNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Users,Orders",
                }
            },
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    {"Ref": "ServiceNames"},  # Parameter reference
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }
        mock_yaml_parse.return_value = original_template

        # Mock the exported template (after artifact upload)
        exported_template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Parameters": {
                "ServiceNames": {
                    "Type": "CommaDelimitedList",
                    "Default": "Users,Orders",
                }
            },
            "Resources": {
                "UsersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/users-abc123.zip",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                },
                "OrdersService": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": "s3://bucket/orders-def456.zip",
                        "Handler": "index.handler",
                        "Runtime": "python3.9",
                    },
                },
            },
        }
        mock_template_instance = Mock()
        mock_template_instance.export.return_value = exported_template
        mock_template_class.return_value = mock_template_instance

        # Mock file open
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = ""

        # Call _export
        package_context._export("template.yaml", use_json=False)

        # Verify warning was emitted
        # Find the secho call with the warning message
        warning_calls = [
            call
            for call in mock_click.secho.call_args_list
            if call[1].get("fg") == "yellow" and "Collection values are fixed at package time" in call[0][0]
        ]
        self.assertEqual(len(warning_calls), 1)

        # Verify warning message content
        warning_msg = warning_calls[0][0][0]
        self.assertIn("Fn::ForEach 'Services'", warning_msg)
        self.assertIn("!Ref ServiceNames", warning_msg)


class TestPackageContextMappingKeyValidation(TestCase):
    """Test cases for CloudFormation Mapping key validation in PackageContext"""

    def test_validate_mapping_key_compatibility_valid_alphanumeric(self):
        """Test that alphanumeric collection values pass validation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["Users", "Orders", "Products123"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        # Should not raise any exception
        _validate_mapping_key_compatibility(prop)

    def test_validate_mapping_key_compatibility_valid_with_hyphens(self):
        """Test that collection values with hyphens pass validation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user-service", "order-service", "product-api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        # Should not raise any exception
        _validate_mapping_key_compatibility(prop)

    def test_validate_mapping_key_compatibility_valid_with_underscores(self):
        """Test that collection values with underscores pass validation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user_service", "order_service", "product_api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        # Should not raise any exception
        _validate_mapping_key_compatibility(prop)

    def test_validate_mapping_key_compatibility_valid_mixed_characters(self):
        """Test that collection values with mixed valid characters pass validation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["User-Service_v1", "Order_API-2", "Product123-test_v2"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        # Should not raise any exception
        _validate_mapping_key_compatibility(prop)

    def test_validate_mapping_key_compatibility_invalid_with_dots(self):
        """Test that collection values with dots raise InvalidMappingKeyError"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user.service", "order.api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        # Verify error message contains the invalid values
        self.assertIn("user.service", str(context.exception))
        self.assertIn("order.api", str(context.exception))
        self.assertIn("Services", str(context.exception))

    def test_validate_mapping_key_compatibility_invalid_with_slashes(self):
        """Test that collection values with slashes raise InvalidMappingKeyError"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user/service", "order/api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        # Verify error message contains the invalid values
        self.assertIn("user/service", str(context.exception))
        self.assertIn("order/api", str(context.exception))

    def test_validate_mapping_key_compatibility_invalid_with_spaces(self):
        """Test that collection values with spaces raise InvalidMappingKeyError"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user service", "order api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        # Verify error message contains the invalid values
        self.assertIn("user service", str(context.exception))
        self.assertIn("order api", str(context.exception))

    def test_validate_mapping_key_compatibility_invalid_with_special_chars(self):
        """Test that collection values with special characters raise InvalidMappingKeyError"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user@service", "order#api", "product$v1"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        # Verify error message contains the invalid values
        self.assertIn("user@service", str(context.exception))
        self.assertIn("order#api", str(context.exception))
        self.assertIn("product$v1", str(context.exception))

    def test_validate_mapping_key_compatibility_mixed_valid_and_invalid(self):
        """Test that only invalid values are reported when mixed with valid values"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["valid-service", "invalid.service", "another_valid", "bad/service"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        error_message = str(context.exception)
        # Verify only invalid values are in the error message
        self.assertIn("invalid.service", error_message)
        self.assertIn("bad/service", error_message)
        # Valid values should not be mentioned as invalid
        self.assertNotIn('"valid-service"', error_message)
        self.assertNotIn('"another_valid"', error_message)

    def test_validate_mapping_key_compatibility_error_message_format(self):
        """Test that error message has the expected format with helpful guidance"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::MyLoop",
            loop_name="MyLoop",
            loop_variable="Item",
            collection=["bad.value"],
            resource_key="${Item}Resource",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${Item}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        error_message = str(context.exception)
        # Verify error message contains helpful information
        self.assertIn("MyLoop", error_message)  # Loop name
        self.assertIn("bad.value", error_message)  # Invalid value
        self.assertIn("alphanumeric", error_message)  # Guidance about valid characters
        self.assertIn("hyphens", error_message)  # Guidance about valid characters
        self.assertIn("underscores", error_message)  # Guidance about valid characters

    def test_validate_mapping_key_compatibility_empty_collection(self):
        """Test that empty collection passes validation (no values to validate)"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=[],  # Empty collection
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        # Should not raise any exception
        _validate_mapping_key_compatibility(prop)


class TestInvalidMappingKeyError(TestCase):
    """Test cases for InvalidMappingKeyError exception"""

    def test_invalid_mapping_key_error_single_value(self):
        """Test InvalidMappingKeyError with a single invalid value"""
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        error = InvalidMappingKeyError(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            invalid_values=["bad.value"],
        )

        error_message = str(error)
        self.assertIn("Services", error_message)
        self.assertIn('"bad.value"', error_message)
        self.assertIn("alphanumeric", error_message)

    def test_invalid_mapping_key_error_multiple_values(self):
        """Test InvalidMappingKeyError with multiple invalid values"""
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        error = InvalidMappingKeyError(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            invalid_values=["bad.value", "another/bad", "third@invalid"],
        )

        error_message = str(error)
        self.assertIn("Services", error_message)
        self.assertIn('"bad.value"', error_message)
        self.assertIn('"another/bad"', error_message)
        self.assertIn('"third@invalid"', error_message)

    def test_invalid_mapping_key_error_attributes(self):
        """Test that InvalidMappingKeyError stores attributes correctly"""
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        error = InvalidMappingKeyError(
            foreach_key="Fn::ForEach::MyLoop",
            loop_name="MyLoop",
            invalid_values=["val1", "val2"],
        )

        self.assertEqual(error.foreach_key, "Fn::ForEach::MyLoop")
        self.assertEqual(error.loop_name, "MyLoop")
        self.assertEqual(error.invalid_values, ["val1", "val2"])


class TestMappingsTransformation(TestCase):
    """
    Comprehensive unit tests for Mappings transformation functionality.

    **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 4.10**

    These tests verify:
    1. Mappings section generation with correct naming convention (4.6)
    2. Fn::FindInMap replacement of dynamic artifact property (4.4)
    3. Fn::ForEach structure preserved after transformation (4.5)
    4. Content-based S3 hash keys are unique per artifact (4.2)
    5. Warning emitted for parameter-based collections (4.8)
    6. Error for invalid Mapping key characters in collection values (4.10)
    """

    # =========================================================================
    # Tests for Mappings section generation with correct naming convention
    # Validates: Requirement 4.6
    # =========================================================================

    def test_mappings_naming_convention_codeuri_services(self):
        """Test Mappings naming convention: SAM{PropertyName}{LoopName} for CodeUri/Services"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
            )
        ]

        exported_resources = {
            "UsersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users.zip"},
            },
            "OrdersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders.zip"},
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify naming convention: SAMCodeUriServices
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertEqual(len(mappings), 1)

    def test_mappings_naming_convention_contenturi_layers(self):
        """Test Mappings naming convention: SAM{PropertyName}{LoopName} for ContentUri/Layers"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Layers",
                loop_name="Layers",
                loop_variable="LayerName",
                collection=["Common", "Utils"],
                resource_key="${LayerName}Layer",
                resource_type="AWS::Serverless::LayerVersion",
                property_name="ContentUri",
                property_value="./layers/${LayerName}",
            )
        ]

        exported_resources = {
            "CommonLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {"ContentUri": "s3://bucket/common.zip"},
            },
            "UtilsLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {"ContentUri": "s3://bucket/utils.zip"},
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify naming convention: SAMContentUriLayers
        self.assertIn("SAMContentUriLayers", mappings)
        self.assertEqual(len(mappings), 1)

    def test_mappings_naming_convention_definitionuri_apis(self):
        """Test Mappings naming convention: SAM{PropertyName}{LoopName} for DefinitionUri/APIs"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::APIs",
                loop_name="APIs",
                loop_variable="ApiName",
                collection=["Users", "Orders"],
                resource_key="${ApiName}Api",
                resource_type="AWS::Serverless::Api",
                property_name="DefinitionUri",
                property_value="./api/${ApiName}/openapi.yaml",
            )
        ]

        exported_resources = {
            "UsersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/users-api.yaml"},
            },
            "OrdersApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"DefinitionUri": "s3://bucket/orders-api.yaml"},
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify naming convention: SAMDefinitionUriAPIs
        self.assertIn("SAMDefinitionUriAPIs", mappings)
        self.assertEqual(len(mappings), 1)

    def test_mappings_naming_convention_multiple_properties(self):
        """Test that multiple dynamic properties generate separate Mappings with correct names"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Function",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./functions/${Name}",
            ),
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Layer",
                resource_type="AWS::Serverless::LayerVersion",
                property_name="ContentUri",
                property_value="./layers/${Name}",
            ),
        ]

        exported_resources = {
            "UsersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users-func.zip"},
            },
            "OrdersFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders-func.zip"},
            },
            "UsersLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {"ContentUri": "s3://bucket/users-layer.zip"},
            },
            "OrdersLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {"ContentUri": "s3://bucket/orders-layer.zip"},
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify both Mappings are created with correct names
        self.assertIn("SAMCodeUriServices", mappings)
        self.assertIn("SAMContentUriServices", mappings)
        self.assertEqual(len(mappings), 2)

    # =========================================================================
    # Tests for Fn::FindInMap replacement of dynamic artifact property
    # Validates: Requirement 4.4
    # =========================================================================

    def test_findmap_replacement_correct_structure(self):
        """Test that Fn::FindInMap replacement has correct structure"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Services": [
                "Name",
                ["Users", "Orders"],
                {
                    "${Name}Service": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./services/${Name}",
                            "Handler": "index.handler",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["Users", "Orders"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        result = _replace_dynamic_artifact_with_findmap(resources, prop)

        self.assertTrue(result)

        # Verify Fn::FindInMap structure
        body = resources["Fn::ForEach::Services"][2]
        code_uri = body["${Name}Service"]["Properties"]["CodeUri"]

        # Verify it's a dict with Fn::FindInMap key
        self.assertIsInstance(code_uri, dict)
        self.assertIn("Fn::FindInMap", code_uri)

        # Verify Fn::FindInMap has exactly 3 elements
        findmap_args = code_uri["Fn::FindInMap"]
        self.assertEqual(len(findmap_args), 3)

        # Verify the structure: [MappingName, LoopVariable, PropertyName]
        self.assertEqual(findmap_args[0], "SAMCodeUriServices")  # Mapping name
        self.assertEqual(findmap_args[1], {"Ref": "Name"})  # Loop variable reference
        self.assertEqual(findmap_args[2], "CodeUri")  # Property name

    def test_findmap_replacement_uses_loop_variable_reference(self):
        """Test that Fn::FindInMap uses the loop variable as second-level key"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Functions": [
                "FuncName",  # Different loop variable name
                ["Alpha", "Beta"],
                {
                    "${FuncName}Function": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./${FuncName}",
                            "Handler": "index.handler",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Functions",
            loop_name="Functions",
            loop_variable="FuncName",
            collection=["Alpha", "Beta"],
            resource_key="${FuncName}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./${FuncName}",
        )

        _replace_dynamic_artifact_with_findmap(resources, prop)

        body = resources["Fn::ForEach::Functions"][2]
        code_uri = body["${FuncName}Function"]["Properties"]["CodeUri"]

        # Verify the loop variable reference uses the correct variable name
        self.assertEqual(code_uri["Fn::FindInMap"][1], {"Ref": "FuncName"})

    # =========================================================================
    # Tests for Fn::ForEach structure preserved after transformation
    # Validates: Requirement 4.5
    # =========================================================================

    def test_foreach_structure_preserved_loop_variable(self):
        """Test that loop variable is preserved after transformation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Services": [
                "ServiceName",  # Original loop variable
                ["Users", "Orders"],
                {
                    "${ServiceName}Service": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./services/${ServiceName}",
                            "Handler": "index.handler",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="ServiceName",
            collection=["Users", "Orders"],
            resource_key="${ServiceName}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${ServiceName}",
        )

        _replace_dynamic_artifact_with_findmap(resources, prop)

        # Verify loop variable is preserved
        self.assertEqual(resources["Fn::ForEach::Services"][0], "ServiceName")

    def test_foreach_structure_preserved_collection(self):
        """Test that collection is preserved after transformation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        original_collection = ["Users", "Orders", "Products"]
        resources = {
            "Fn::ForEach::Services": [
                "Name",
                original_collection.copy(),
                {
                    "${Name}Service": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./services/${Name}",
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=original_collection,
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        _replace_dynamic_artifact_with_findmap(resources, prop)

        # Verify collection is preserved
        self.assertEqual(resources["Fn::ForEach::Services"][1], original_collection)

    def test_foreach_structure_preserved_other_properties(self):
        """Test that other properties in the resource are preserved after transformation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Services": [
                "Name",
                ["Users", "Orders"],
                {
                    "${Name}Service": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./services/${Name}",
                            "Handler": "${Name}.handler",  # Dynamic handler
                            "Runtime": "python3.9",  # Static property
                            "MemorySize": 256,  # Static property
                            "Environment": {
                                "Variables": {
                                    "SERVICE_NAME": "${Name}",  # Dynamic env var
                                }
                            },
                        },
                    }
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["Users", "Orders"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        _replace_dynamic_artifact_with_findmap(resources, prop)

        body = resources["Fn::ForEach::Services"][2]
        props = body["${Name}Service"]["Properties"]

        # Verify other properties are preserved
        self.assertEqual(props["Handler"], "${Name}.handler")
        self.assertEqual(props["Runtime"], "python3.9")
        self.assertEqual(props["MemorySize"], 256)
        self.assertEqual(props["Environment"]["Variables"]["SERVICE_NAME"], "${Name}")

    def test_foreach_structure_preserved_multiple_resources(self):
        """Test that multiple resources in ForEach body are preserved"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        resources = {
            "Fn::ForEach::Services": [
                "Name",
                ["Users", "Orders"],
                {
                    "${Name}Function": {
                        "Type": "AWS::Serverless::Function",
                        "Properties": {
                            "CodeUri": "./functions/${Name}",
                            "Handler": "index.handler",
                        },
                    },
                    "${Name}Table": {
                        "Type": "AWS::DynamoDB::Table",
                        "Properties": {
                            "TableName": "${Name}Table",
                        },
                    },
                },
            ]
        }

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["Users", "Orders"],
            resource_key="${Name}Function",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./functions/${Name}",
        )

        _replace_dynamic_artifact_with_findmap(resources, prop)

        body = resources["Fn::ForEach::Services"][2]

        # Verify both resources are preserved
        self.assertIn("${Name}Function", body)
        self.assertIn("${Name}Table", body)

        # Verify DynamoDB table is unchanged
        self.assertEqual(body["${Name}Table"]["Type"], "AWS::DynamoDB::Table")
        self.assertEqual(body["${Name}Table"]["Properties"]["TableName"], "${Name}Table")

    # =========================================================================
    # Tests for content-based S3 hash keys are unique per artifact
    # Validates: Requirement 4.2
    # =========================================================================

    def test_s3_hash_keys_unique_per_artifact(self):
        """Test that each artifact gets a unique S3 URI based on content hash"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders", "Products"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
            )
        ]

        # Simulate exported resources with unique content-based hashes
        exported_resources = {
            "UsersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/abc123def456.zip",  # Unique hash
                },
            },
            "OrdersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/789ghi012jkl.zip",  # Different unique hash
                },
            },
            "ProductsService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "s3://bucket/mno345pqr678.zip",  # Another unique hash
                },
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify each collection value has a unique S3 URI
        users_uri = mappings["SAMCodeUriServices"]["Users"]["CodeUri"]
        orders_uri = mappings["SAMCodeUriServices"]["Orders"]["CodeUri"]
        products_uri = mappings["SAMCodeUriServices"]["Products"]["CodeUri"]

        # All URIs should be different (unique content-based hashes)
        self.assertNotEqual(users_uri, orders_uri)
        self.assertNotEqual(users_uri, products_uri)
        self.assertNotEqual(orders_uri, products_uri)

        # Verify the URIs match the exported resources
        self.assertEqual(users_uri, "s3://bucket/abc123def456.zip")
        self.assertEqual(orders_uri, "s3://bucket/789ghi012jkl.zip")
        self.assertEqual(products_uri, "s3://bucket/mno345pqr678.zip")

    def test_s3_hash_keys_preserved_in_mappings(self):
        """Test that S3 URIs with content hashes are correctly stored in Mappings"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Layers",
                loop_name="Layers",
                loop_variable="LayerName",
                collection=["Common", "Utils"],
                resource_key="${LayerName}Layer",
                resource_type="AWS::Serverless::LayerVersion",
                property_name="ContentUri",
                property_value="./layers/${LayerName}",
            )
        ]

        # Simulate exported resources with content-based hashes
        exported_resources = {
            "CommonLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "ContentUri": "s3://my-bucket/prefix/common-layer-a1b2c3d4e5f6.zip",
                },
            },
            "UtilsLayer": {
                "Type": "AWS::Serverless::LayerVersion",
                "Properties": {
                    "ContentUri": "s3://my-bucket/prefix/utils-layer-g7h8i9j0k1l2.zip",
                },
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify the full S3 URIs with hashes are preserved
        self.assertEqual(
            mappings["SAMContentUriLayers"]["Common"]["ContentUri"],
            "s3://my-bucket/prefix/common-layer-a1b2c3d4e5f6.zip",
        )
        self.assertEqual(
            mappings["SAMContentUriLayers"]["Utils"]["ContentUri"], "s3://my-bucket/prefix/utils-layer-g7h8i9j0k1l2.zip"
        )

    # =========================================================================
    # Tests for warning emitted for parameter-based collections
    # Validates: Requirement 4.8
    # =========================================================================

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_warning_emitted_for_parameter_based_collection_with_dynamic_codeuri(self, mock_click):
        """Test that warning is emitted when using parameter-based collection with dynamic CodeUri"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
                collection_is_parameter_ref=True,
                collection_parameter_name="ServiceNames",
            )
        ]

        warn_parameter_based_collections(dynamic_properties)

        # Verify warning was emitted
        mock_click.secho.assert_called_once()
        warning_msg = mock_click.secho.call_args[0][0]

        # Verify warning message contains key information
        self.assertIn("Services", warning_msg)
        self.assertIn("CodeUri", warning_msg)
        self.assertIn("ServiceNames", warning_msg)
        self.assertIn("fixed at package time", warning_msg)
        self.assertIn("re-package", warning_msg)

    @patch("samcli.lib.package.language_extensions_packaging.click")
    def test_no_warning_for_static_list_collection(self, mock_click):
        """Test that no warning is emitted for static list collections"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
                collection_is_parameter_ref=False,  # Static list
                collection_parameter_name=None,
            )
        ]

        warn_parameter_based_collections(dynamic_properties)

        # Verify no warning was emitted
        mock_click.secho.assert_not_called()

    # =========================================================================
    # Tests for error for invalid Mapping key characters in collection values
    # Validates: Requirement 4.10
    # =========================================================================

    def test_error_for_invalid_mapping_key_with_dots(self):
        """Test that error is raised for collection values with dots"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user.service", "order.api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError) as context:
            _validate_mapping_key_compatibility(prop)

        error_msg = str(context.exception)
        self.assertIn("user.service", error_msg)
        self.assertIn("order.api", error_msg)
        self.assertIn("Services", error_msg)

    def test_error_for_invalid_mapping_key_with_slashes(self):
        """Test that error is raised for collection values with slashes"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty
        from samcli.commands.package.exceptions import InvalidMappingKeyError

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user/service", "order/api"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        with self.assertRaises(InvalidMappingKeyError):
            _validate_mapping_key_compatibility(prop)

    def test_valid_mapping_keys_pass_validation(self):
        """Test that valid collection values pass validation"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        prop = DynamicArtifactProperty(
            foreach_key="Fn::ForEach::Services",
            loop_name="Services",
            loop_variable="Name",
            collection=["user-service", "order_api", "Product123"],
            resource_key="${Name}Service",
            resource_type="AWS::Serverless::Function",
            property_name="CodeUri",
            property_value="./services/${Name}",
        )

        # Should not raise any exception
        _validate_mapping_key_compatibility(prop)

    # =========================================================================
    # Integration tests for complete Mappings transformation flow
    # =========================================================================

    def test_full_mappings_transformation_flow(self):
        """Test the complete flow: detect -> generate mappings -> apply to template"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        # Original template with dynamic CodeUri
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                                "Handler": "index.handler",
                                "Runtime": "python3.9",
                            },
                        }
                    },
                ]
            },
        }

        # Step 1: Detect dynamic properties
        dynamic_properties = detect_dynamic_artifact_properties(template)
        self.assertEqual(len(dynamic_properties), 1)

        # Step 2: Simulate exported resources
        exported_resources = {
            "UsersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/users-hash123.zip"},
            },
            "OrdersService": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/orders-hash456.zip"},
            },
        }

        # Step 3: Generate Mappings
        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Step 4: Apply Mappings to template
        result = _apply_artifact_mappings_to_template(template, mappings, dynamic_properties)

        # Verify Mappings section was added
        self.assertIn("Mappings", result)
        self.assertIn("SAMCodeUriServices", result["Mappings"])

        # Verify Mappings content
        self.assertEqual(result["Mappings"]["SAMCodeUriServices"]["Users"]["CodeUri"], "s3://bucket/users-hash123.zip")
        self.assertEqual(
            result["Mappings"]["SAMCodeUriServices"]["Orders"]["CodeUri"], "s3://bucket/orders-hash456.zip"
        )

        # Verify Fn::ForEach structure is preserved
        self.assertIn("Fn::ForEach::Services", result["Resources"])

        # Verify CodeUri was replaced with Fn::FindInMap
        body = result["Resources"]["Fn::ForEach::Services"][2]
        code_uri = body["${Name}Service"]["Properties"]["CodeUri"]
        self.assertEqual(code_uri, {"Fn::FindInMap": ["SAMCodeUriServices", {"Ref": "Name"}, "CodeUri"]})

        # Verify other properties are preserved
        self.assertEqual(body["${Name}Service"]["Properties"]["Handler"], "index.handler")
        self.assertEqual(body["${Name}Service"]["Properties"]["Runtime"], "python3.9")

    def test_mappings_transformation_with_existing_mappings(self):
        """Test that generated Mappings are merged with existing Mappings"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        # Template with existing Mappings
        template = {
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Mappings": {
                "ExistingMapping": {
                    "Key1": {"Value": "existing-value-1"},
                    "Key2": {"Value": "existing-value-2"},
                }
            },
            "Resources": {
                "Fn::ForEach::Services": [
                    "Name",
                    ["Users", "Orders"],
                    {
                        "${Name}Service": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "CodeUri": "./services/${Name}",
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Services",
                loop_name="Services",
                loop_variable="Name",
                collection=["Users", "Orders"],
                resource_key="${Name}Service",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value="./services/${Name}",
            )
        ]

        mappings = {
            "SAMCodeUriServices": {
                "Users": {"CodeUri": "s3://bucket/users.zip"},
                "Orders": {"CodeUri": "s3://bucket/orders.zip"},
            }
        }

        result = _apply_artifact_mappings_to_template(template, mappings, dynamic_properties)

        # Verify both existing and new Mappings are present
        self.assertIn("ExistingMapping", result["Mappings"])
        self.assertIn("SAMCodeUriServices", result["Mappings"])

        # Verify existing Mappings are unchanged
        self.assertEqual(result["Mappings"]["ExistingMapping"]["Key1"]["Value"], "existing-value-1")

    def test_mappings_transformation_with_lambda_function_code(self):
        """Test Mappings transformation for AWS::Lambda::Function Code property"""
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Functions",
                loop_name="Functions",
                loop_variable="Name",
                collection=["Alpha", "Beta"],
                resource_key="${Name}Function",
                resource_type="AWS::Lambda::Function",
                property_name="Code",
                property_value="./functions/${Name}",
            )
        ]

        # Lambda Function Code property can be a dict with S3Bucket/S3Key
        exported_resources = {
            "AlphaFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"S3Bucket": "my-bucket", "S3Key": "alpha-code.zip"},
                },
            },
            "BetaFunction": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"S3Bucket": "my-bucket", "S3Key": "beta-code.zip"},
                },
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        # Verify S3 URIs are constructed correctly from S3Bucket/S3Key
        self.assertEqual(mappings["SAMCodeFunctions"]["Alpha"]["Code"], "s3://my-bucket/alpha-code.zip")
        self.assertEqual(mappings["SAMCodeFunctions"]["Beta"]["Code"], "s3://my-bucket/beta-code.zip")


class TestBuildToPackageFlow(TestCase):
    """
    Tests verifying that sam package correctly handles build output templates
    that already contain Mappings from sam build's dynamic artifact handling.

    When sam build processes a template with dynamic CodeUri (e.g., CodeUri: ${Name}/),
    it generates Mappings with build artifact paths and replaces CodeUri with Fn::FindInMap.
    sam package must detect this Fn::FindInMap as dynamic and regenerate Mappings with S3 URIs.

    Validates Requirements: 6.6, 12.1
    """

    def test_findmap_codeuri_detected_as_dynamic(self):
        """
        Verify that Fn::FindInMap containing loop variable is detected as dynamic.

        After sam build, CodeUri becomes:
          Fn::FindInMap: [SAMCodeUriFunctions, {Ref: FunctionName}, CodeUri]

        contains_loop_variable should detect {"Ref": "FunctionName"} in the list.
        """
        findmap_value = {"Fn::FindInMap": ["SAMCodeUriFunctions", {"Ref": "FunctionName"}, "CodeUri"]}

        self.assertTrue(
            contains_loop_variable(findmap_value, "FunctionName"),
            "Fn::FindInMap with {Ref: FunctionName} should be detected as containing loop variable",
        )

    def test_findmap_codeuri_without_loop_variable_not_detected(self):
        """Verify Fn::FindInMap without loop variable is not detected as dynamic."""
        findmap_value = {"Fn::FindInMap": ["SomeMapping", "StaticKey", "CodeUri"]}

        self.assertFalse(
            contains_loop_variable(findmap_value, "FunctionName"),
            "Fn::FindInMap without loop variable should not be detected as dynamic",
        )

    def test_detect_dynamic_properties_from_build_output(self):
        """
        Verify _detect_dynamic_artifact_properties correctly detects Fn::FindInMap
        as dynamic when processing a build output template.

        This simulates the template that sam build produces:
        - Mappings section with SAMCodeUriFunctions containing build paths
        - CodeUri replaced with Fn::FindInMap
        """
        # Template as produced by sam build (with Mappings and Fn::FindInMap)
        build_output_template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": ["AWS::LanguageExtensions", "AWS::Serverless-2016-10-31"],
            "Mappings": {
                "SAMCodeUriFunctions": {
                    "Alpha": {"CodeUri": "AlphaFunction/"},
                    "Beta": {"CodeUri": "BetaFunction/"},
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FunctionName",
                    ["Alpha", "Beta"],
                    {
                        "${FunctionName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "main.handler",
                                "CodeUri": {
                                    "Fn::FindInMap": [
                                        "SAMCodeUriFunctions",
                                        {"Ref": "FunctionName"},
                                        "CodeUri",
                                    ]
                                },
                            },
                        }
                    },
                ]
            },
        }

        dynamic_properties = detect_dynamic_artifact_properties(build_output_template)

        self.assertEqual(len(dynamic_properties), 1, "Should detect one dynamic artifact property")

        prop = dynamic_properties[0]
        self.assertEqual(prop.foreach_key, "Fn::ForEach::Functions")
        self.assertEqual(prop.loop_variable, "FunctionName")
        self.assertEqual(prop.property_name, "CodeUri")
        self.assertEqual(prop.collection, ["Alpha", "Beta"])

    def test_generate_mappings_overwrites_build_mappings_with_s3_uris(self):
        """
        Verify that _generate_artifact_mappings produces S3 URIs that will
        overwrite the build-time Mappings when applied to the template.
        """
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Functions",
                loop_name="Functions",
                loop_variable="FunctionName",
                collection=["Alpha", "Beta"],
                resource_key="${FunctionName}Function",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value={"Fn::FindInMap": ["SAMCodeUriFunctions", {"Ref": "FunctionName"}, "CodeUri"]},
            )
        ]

        exported_resources = {
            "AlphaFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/alpha-abc123.zip"},
            },
            "BetaFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {"CodeUri": "s3://bucket/beta-def456.zip"},
            },
        }

        mappings, _ = _generate_artifact_mappings(dynamic_properties, "/tmp", exported_resources)

        self.assertIn("SAMCodeUriFunctions", mappings)
        self.assertEqual(
            mappings["SAMCodeUriFunctions"]["Alpha"]["CodeUri"],
            "s3://bucket/alpha-abc123.zip",
        )
        self.assertEqual(
            mappings["SAMCodeUriFunctions"]["Beta"]["CodeUri"],
            "s3://bucket/beta-def456.zip",
        )

    def test_apply_mappings_replaces_build_mappings(self):
        """
        Verify that _apply_artifact_mappings_to_template correctly replaces
        build-time Mappings with S3 URI Mappings in the output template.
        """
        from samcli.lib.cfn_language_extensions.models import DynamicArtifactProperty

        # Template with build-time Mappings
        template = {
            "Mappings": {
                "SAMCodeUriFunctions": {
                    "Alpha": {"CodeUri": "AlphaFunction/"},
                    "Beta": {"CodeUri": "BetaFunction/"},
                }
            },
            "Resources": {
                "Fn::ForEach::Functions": [
                    "FunctionName",
                    ["Alpha", "Beta"],
                    {
                        "${FunctionName}Function": {
                            "Type": "AWS::Serverless::Function",
                            "Properties": {
                                "Handler": "main.handler",
                                "CodeUri": {
                                    "Fn::FindInMap": [
                                        "SAMCodeUriFunctions",
                                        {"Ref": "FunctionName"},
                                        "CodeUri",
                                    ]
                                },
                            },
                        }
                    },
                ]
            },
        }

        # New Mappings with S3 URIs
        new_mappings = {
            "SAMCodeUriFunctions": {
                "Alpha": {"CodeUri": "s3://bucket/alpha-abc123.zip"},
                "Beta": {"CodeUri": "s3://bucket/beta-def456.zip"},
            }
        }

        dynamic_properties = [
            DynamicArtifactProperty(
                foreach_key="Fn::ForEach::Functions",
                loop_name="Functions",
                loop_variable="FunctionName",
                collection=["Alpha", "Beta"],
                resource_key="${FunctionName}Function",
                resource_type="AWS::Serverless::Function",
                property_name="CodeUri",
                property_value={"Fn::FindInMap": ["SAMCodeUriFunctions", {"Ref": "FunctionName"}, "CodeUri"]},
            )
        ]

        result = _apply_artifact_mappings_to_template(template, new_mappings, dynamic_properties)

        # Verify Mappings were replaced with S3 URIs
        result_mappings = result.get("Mappings", {})
        self.assertEqual(
            result_mappings["SAMCodeUriFunctions"]["Alpha"]["CodeUri"],
            "s3://bucket/alpha-abc123.zip",
        )
        self.assertEqual(
            result_mappings["SAMCodeUriFunctions"]["Beta"]["CodeUri"],
            "s3://bucket/beta-def456.zip",
        )

        # Verify Fn::FindInMap is preserved in the ForEach body
        foreach_block = result["Resources"]["Fn::ForEach::Functions"]
        body = foreach_block[2]
        codeuri = body["${FunctionName}Function"]["Properties"]["CodeUri"]
        self.assertIn("Fn::FindInMap", codeuri)
        self.assertEqual(codeuri["Fn::FindInMap"][0], "SAMCodeUriFunctions")
