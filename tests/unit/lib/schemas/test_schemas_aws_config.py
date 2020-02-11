""" Test AWS configuration """

from unittest import TestCase
from unittest.mock import patch, ANY

from samcli.commands.local.cli_common.user_exceptions import ResourceNotFound, NotAvailableInRegion
from samcli.lib.schemas.schemas_aws_config import get_aws_configuration_choice


class TestInitAWSConfiguration(TestCase):
    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("click.confirm")
    def test_get_aws_configuration_profile_is_set_to_none_for_default_selection(self, confirm_mock, session_mock):
        confirm_mock.side_effect = [True]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "us-west-2"
        aws_configuration_choice = get_aws_configuration_choice()
        self.assertEqual(aws_configuration_choice["profile"], None),
        self.assertEqual(aws_configuration_choice["region"], "us-west-2")
        confirm_mock.assert_any_call(
            "\nDo you want to use the default AWS profile [default] and region [us-west-2]?", default=True
        )

    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("click.confirm")
    @patch("click.prompt")
    def test_get_aws_configuration_choice_selected(self, prompt_mock, confirm_mock, session_mock):
        confirm_mock.side_effect = [False]
        prompt_mock.side_effect = ["2", "2"]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "us-west-2"
        session_mock.return_value.available_profiles = ["default", "test-profile"]
        aws_configuration_choice = get_aws_configuration_choice()
        self.assertEqual(aws_configuration_choice["profile"], "test-profile"),
        self.assertEqual(aws_configuration_choice["region"], "us-east-2")
        confirm_mock.assert_any_call(
            "\nDo you want to use the default AWS profile [default] and region [us-west-2]?", default=True
        )
        prompt_mock.assert_any_call("Profile", type=ANY, show_choices=False)
        prompt_mock.assert_any_call("Region", type=ANY, show_choices=False)

    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("click.confirm")
    def test_get_aws_configuration_raises_exception_when_no_profile_found(self, confirm_mock, session_mock):
        confirm_mock.side_effect = [False]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "us-west-2"
        session_mock.return_value.available_profiles = []
        with self.assertRaises(ResourceNotFound) as ctx:
            get_aws_configuration_choice()
        msg = "No configured AWS profile found."
        self.assertEqual(str(ctx.exception), msg)

    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("click.confirm")
    @patch("click.prompt")
    def test_get_aws_configuration_raises_exception_when_schema_service_not_available_in_region(
        self, prompt_mock, confirm_mock, session_mock
    ):
        confirm_mock.side_effect = [True]
        prompt_mock.side_effect = ["2"]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "ap-south-1"
        session_mock.return_value.available_profiles = ["default", "test-profile"]
        with self.assertRaises(NotAvailableInRegion) as ctx:
            get_aws_configuration_choice()
        msg = "EventBridge Schemas are not yet available in ap-south-1. Please select one of ['us-west-2', 'us-east-2', 'us-west-2', 'eu-west-1', 'ap-northeast-1']"
        self.assertEqual(str(ctx.exception), msg)
