from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.lib.utils.boto_utils import (
    get_boto_config_with_user_agent,
    get_boto_client_provider_with_config,
    get_boto_resource_provider_with_config,
    get_boto_resource_provider_from_session_with_config,
    get_boto_client_provider_from_session_with_config,
    get_client_error_code,
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
    def test_get_boto_client_provider_from_session_with_config(self, patched_get_config):
        given_client_name = "lambda"
        given_session = Mock()
        given_config_param = Mock()
        given_client = Mock()
        given_config = Mock()

        given_session.client.return_value = given_client
        patched_get_config.return_value = given_config

        client_generator = get_boto_client_provider_from_session_with_config(given_session, param=given_config_param)

        client = client_generator(given_client_name)

        self.assertEqual(client, given_client)
        patched_get_config.assert_called_with(param=given_config_param)
        given_session.client.assert_called_with(given_client_name, config=given_config)

    @patch("samcli.lib.utils.boto_utils.get_boto_client_provider_from_session_with_config")
    @patch("samcli.lib.utils.boto_utils.Session")
    def test_get_boto_client_provider_with_config(self, patched_session, patched_get_client):
        given_session = Mock()
        patched_session.return_value = given_session

        given_client_generator = Mock()
        patched_get_client.return_value = given_client_generator

        given_config_param = Mock()
        given_profile = Mock()
        given_region = Mock()

        client_generator = get_boto_client_provider_with_config(
            region=given_region, profile=given_profile, param=given_config_param
        )

        patched_session.assert_called_with(region_name=given_region, profile_name=given_profile)
        patched_get_client.assert_called_with(given_session, param=given_config_param)
        self.assertEqual(given_client_generator, client_generator)

    @patch("samcli.lib.utils.boto_utils.get_boto_resource_provider_from_session_with_config")
    @patch("samcli.lib.utils.boto_utils.Session")
    def test_get_boto_resource_provider_with_config(self, patched_session, patched_get_resource):
        given_session = Mock()
        patched_session.return_value = given_session

        given_resource_generator = Mock()
        patched_get_resource.return_value = given_resource_generator

        given_config_param = Mock()
        given_profile = Mock()
        given_region = Mock()

        client_generator = get_boto_resource_provider_with_config(
            region=given_region, profile=given_profile, param=given_config_param
        )

        patched_session.assert_called_with(region_name=given_region, profile_name=given_profile)
        patched_get_resource.assert_called_with(given_session, param=given_config_param)
        self.assertEqual(given_resource_generator, client_generator)

    @patch("samcli.lib.utils.boto_utils.get_boto_config_with_user_agent")
    def test_get_boto_resource_provider_from_session_with_config(self, patched_get_config):
        given_resource_name = "cloudformation"
        given_session = Mock()
        given_config_param = Mock()
        given_resource = Mock()
        given_config = Mock()

        given_session.resource.return_value = given_resource
        patched_get_config.return_value = given_config

        resource_generator = get_boto_resource_provider_from_session_with_config(
            given_session, param=given_config_param
        )

        resource = resource_generator(given_resource_name)

        self.assertEqual(resource, given_resource)
        patched_get_config.assert_called_with(param=given_config_param)
        given_session.resource.assert_called_with(given_resource_name, config=given_config)

    @parameterized.expand([({}, None), ({"Error": {}}, None), ({"Error": {"Code": "ErrorCode"}}, "ErrorCode")])
    def test_get_client_error_code(self, response, expected):
        self.assertEqual(expected, get_client_error_code(Mock(response=response)))
