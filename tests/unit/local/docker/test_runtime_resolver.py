from unittest import TestCase
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

from samcli.commands.local.cli_common.user_exceptions import CredentialsRequired, ResourceNotFound
from samcli.lib.build.constants import CUSTOM_RUNTIME
from samcli.local.docker.exceptions import RuntimeResolutionException
from samcli.local.docker.runtime_resolver import resolve_custom_runtime_image


class TestResolveCustomRuntimeImage(TestCase):
    def setUp(self):
        self.runtime_arn = "arn:aws:lambda:us-east-1:123456789012:runtime/my-runtime"
        self.runtime_config = {"RuntimeArn": self.runtime_arn, "RuntimeAlias": "live"}
        self.lambda_client_mock = Mock()
        self.lambda_client_mock.get_runtime_alias.return_value = {"RuntimeVersion": "3"}
        self.lambda_client_mock.get_runtime_version.return_value = {
            "ResolvedUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-runtime@sha256:abc"
        }

    def test_custom_runtime_constant(self):
        self.assertEqual(CUSTOM_RUNTIME, "custom")

    def test_returns_supplied_image_when_present(self):
        result = resolve_custom_runtime_image(self.runtime_config, "my-cmr-image:local", self.lambda_client_mock)
        self.assertEqual(result, "my-cmr-image:local")
        self.lambda_client_mock.get_runtime_alias.assert_not_called()

    def test_returns_supplied_image_without_runtime_config(self):
        # A supplied image wins even if no RuntimeConfig is present.
        result = resolve_custom_runtime_image(None, "my-cmr-image:local")
        self.assertEqual(result, "my-cmr-image:local")

    def test_resolves_image_from_runtime_config(self):
        result = resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertEqual(result, "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-runtime@sha256:abc")
        self.lambda_client_mock.get_runtime_alias.assert_called_once_with(RuntimeName=self.runtime_arn, Name="live")
        self.lambda_client_mock.get_runtime_version.assert_called_once_with(RuntimeName=self.runtime_arn, Name="3")

    @patch("samcli.local.docker.runtime_resolver.boto3")
    def test_creates_lambda_client_in_runtime_region_when_not_provided(self, boto3_mock):
        # A runtime is only known in the region its ARN names, whatever the default region is.
        boto3_mock.client.return_value = self.lambda_client_mock
        runtime_config = {
            "RuntimeArn": "arn:aws:lambda:eu-west-1:123456789012:runtime/my-runtime",
            "RuntimeAlias": "live",
        }

        resolve_custom_runtime_image(runtime_config, None)

        boto3_mock.client.assert_called_once_with("lambda-core", region_name="eu-west-1")

    @patch("samcli.local.docker.runtime_resolver.boto3")
    def test_uses_default_region_when_runtime_arn_has_no_region(self, boto3_mock):
        boto3_mock.client.return_value = self.lambda_client_mock

        resolve_custom_runtime_image({"RuntimeArn": "my-runtime", "RuntimeAlias": "live"}, None)

        boto3_mock.client.assert_called_once_with("lambda-core", region_name=None)

    @patch("samcli.local.docker.runtime_resolver.boto3")
    def test_uses_default_region_when_runtime_arn_region_is_empty(self, boto3_mock):
        boto3_mock.client.return_value = self.lambda_client_mock

        resolve_custom_runtime_image(
            {"RuntimeArn": "arn:aws:lambda::123456789012:runtime/my-runtime", "RuntimeAlias": "live"}, None
        )

        boto3_mock.client.assert_called_once_with("lambda-core", region_name=None)

    def test_logs_resolved_image(self):
        with self.assertLogs("samcli.local.docker.runtime_resolver", level="INFO") as logs:
            resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertIn(
            "Using runtime image 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-runtime@sha256:abc "
            "(RuntimeAlias 'live')",
            logs.output[0],
        )

    def test_raises_when_no_image_and_no_runtime_config(self):
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image(None, None)

        self.assertIn("the function has no RuntimeConfig", str(ctx.exception))

    def test_raises_when_no_image_and_empty_runtime_config(self):
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image({}, None)

        self.assertIn("the function has no RuntimeConfig", str(ctx.exception))

    def test_raises_when_runtime_alias_missing(self):
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image({"RuntimeArn": self.runtime_arn}, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception),
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig is missing RuntimeAlias.",
        )
        self.lambda_client_mock.get_runtime_alias.assert_not_called()

    def test_raises_when_runtime_arn_missing(self):
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image({"RuntimeAlias": "live"}, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception),
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig is missing RuntimeArn.",
        )
        self.lambda_client_mock.get_runtime_alias.assert_not_called()

    def test_raises_when_both_fields_missing(self):
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image({"Other": "value"}, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception),
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig is missing "
            "RuntimeArn and RuntimeAlias.",
        )

    def test_raises_when_runtime_alias_empty(self):
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image({"RuntimeArn": self.runtime_arn, "RuntimeAlias": ""}, None)

        self.assertIn("missing RuntimeAlias", str(ctx.exception))

    def test_raises_when_runtime_config_is_not_a_mapping(self):
        # For example RuntimeConfig: !Ref SomeStringParameter, which resolves to a string.
        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image("arn:aws:lambda:us-east-1:123456789012:runtime/my-runtime", None)

        self.assertEqual(
            str(ctx.exception),
            "Unable to resolve an invoke image for the 'custom' runtime: RuntimeConfig must be a mapping "
            "with RuntimeArn and RuntimeAlias.",
        )

    def test_raises_when_runtime_config_itself_is_unresolved_intrinsic(self):
        # RuntimeConfig: !ImportValue SharedRuntimeConfig reaches the resolver as a dict keyed by the intrinsic.
        for runtime_config in ({"Fn::ImportValue": "SharedRuntimeConfig"}, {"Ref": "AWS::NoValue"}):
            with self.subTest(runtime_config=runtime_config):
                with self.assertRaises(RuntimeResolutionException) as ctx:
                    resolve_custom_runtime_image(runtime_config, None, self.lambda_client_mock)

                self.assertIn("RuntimeArn and RuntimeAlias must be literal values", str(ctx.exception))
                self.lambda_client_mock.get_runtime_alias.assert_not_called()

    def test_raises_when_runtime_config_value_is_unresolved_intrinsic(self):
        # An intrinsic SAM CLI cannot resolve locally reaches the resolver as a dict.
        runtime_config = {"RuntimeArn": {"Fn::ImportValue": "SharedRuntimeArn"}, "RuntimeAlias": "live"}

        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image(runtime_config, None, self.lambda_client_mock)

        self.assertIn("RuntimeArn and RuntimeAlias must be literal values", str(ctx.exception))
        self.lambda_client_mock.get_runtime_alias.assert_not_called()

    def test_raises_credentials_required_with_no_creds(self):
        self.lambda_client_mock.get_runtime_alias.side_effect = NoCredentialsError()

        with self.assertRaises(CredentialsRequired) as ctx:
            resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception),
            "Resolving the runtime image for RuntimeConfig requires AWS credentials. Configure credentials, "
            "for example with --profile.",
        )

    def test_raises_credentials_required_with_AccessDeniedException(self):
        self.lambda_client_mock.get_runtime_alias.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException", "Message": "User is not authorized"}},
            operation_name="GetRuntimeAlias",
        )

        with self.assertRaises(CredentialsRequired) as ctx:
            resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception), f"Not allowed to look up runtime {self.runtime_arn} alias live: User is not authorized"
        )

    def test_raises_resource_not_found_with_ResourceNotFoundException(self):
        self.lambda_client_mock.get_runtime_version.side_effect = ClientError(
            error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Runtime version not found"}},
            operation_name="GetRuntimeVersion",
        )

        with self.assertRaises(ResourceNotFound) as ctx:
            resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception), f"Runtime {self.runtime_arn} alias live was not found: Runtime version not found"
        )

    def test_wraps_unknown_client_error(self):
        self.lambda_client_mock.get_runtime_alias.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceException", "Message": "Service unavailable"}},
            operation_name="GetRuntimeAlias",
        )

        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertEqual(
            str(ctx.exception), f"Could not look up runtime {self.runtime_arn} alias live: Service unavailable"
        )

    def test_wraps_error_that_never_reached_lambda(self):
        # For example no network: a botocore error rather than a response from Lambda.
        self.lambda_client_mock.get_runtime_alias.side_effect = EndpointConnectionError(
            endpoint_url="https://lambda.us-east-1.amazonaws.com"
        )

        with self.assertRaises(RuntimeResolutionException) as ctx:
            resolve_custom_runtime_image(self.runtime_config, None, self.lambda_client_mock)

        self.assertIn(f"Could not look up runtime {self.runtime_arn} alias live: ", str(ctx.exception))
        self.assertIn("https://lambda.us-east-1.amazonaws.com", str(ctx.exception))
