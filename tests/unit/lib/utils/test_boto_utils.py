from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.utils.boto_utils import (
    get_boto_config_with_user_agent,
    get_boto_client_provider_with_config,
    get_boto_resource_provider_with_config,
)

TEST_VERSION = "1.0.0"


class TestBotoUtils(TestCase):
    @parameterized.expand([(True,), (False,)])
    @patch("samcli.lib.utils.boto_utils.GlobalConfig")
    @patch("samcli.lib.utils.boto_utils.__version__", TEST_VERSION)
    def test_get_boto_config_with_user_agent(
        self,
        telemetry_enabled,
        patched_global_config,
    ):
        given_global_config_instance = Mock()
        patched_global_config.return_value = given_global_config_instance

        given_global_config_instance.telemetry_enabled = telemetry_enabled
        given_region_name = "us-west-2"

        config = get_boto_config_with_user_agent(region_name=given_region_name)

        self.assertEqual(given_region_name, config.region_name)

        if telemetry_enabled:
            self.assertEqual(
                config.user_agent_extra, f"aws-sam-cli/{TEST_VERSION}/{given_global_config_instance.installation_id}"
            )
        else:
            self.assertEqual(config.user_agent_extra, f"aws-sam-cli/{TEST_VERSION}")

    @patch("samcli.lib.utils.boto_utils.get_boto_config_with_user_agent")
    @patch("samcli.lib.utils.boto_utils.boto3")
    def test_get_boto_client_provider_with_config(self, patched_boto3, patched_get_config):
        given_config = Mock()
        patched_get_config.return_value = given_config

        given_config_param = Mock()
        given_profile = Mock()
        given_region = Mock()
        client_generator = get_boto_client_provider_with_config(
            region=given_region, profile=given_profile, param=given_config_param
        )

        given_service_client = Mock()
        patched_boto3.session.Session().client.return_value = given_service_client

        client = client_generator("service")

        self.assertEqual(client, given_service_client)
        patched_get_config.assert_called_with(param=given_config_param)
        patched_boto3.session.Session.assert_called_with(region_name=given_region, profile_name=given_profile)
        patched_boto3.session.Session().client.assert_called_with("service", config=given_config)

    @patch("samcli.lib.utils.boto_utils.get_boto_config_with_user_agent")
    @patch("samcli.lib.utils.boto_utils.boto3")
    def test_get_boto_resource_provider_with_config(self, patched_boto3, patched_get_config):
        given_config = Mock()
        patched_get_config.return_value = given_config

        given_config_param = Mock()
        given_profile = Mock()
        given_region = Mock()
        client_generator = get_boto_resource_provider_with_config(
            region=given_region, profile=given_profile, param=given_config_param
        )

        given_service_client = Mock()
        patched_boto3.session.Session().resource.return_value = given_service_client

        client = client_generator("service")

        self.assertEqual(client, given_service_client)
        patched_get_config.assert_called_with(param=given_config_param)
        patched_boto3.session.Session.assert_called_with(region_name=given_region, profile_name=given_profile)
        patched_boto3.session.Session().resource.assert_called_with("service", config=given_config)
