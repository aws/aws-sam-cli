""" Test AWS configuration """

from unittest import TestCase
from unittest.mock import patch, ANY, Mock

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
        self.assertEqual(aws_configuration_choice["profile"], None)
        self.assertEqual(aws_configuration_choice["region"], "us-west-2")
        confirm_mock.assert_any_call(
            "\nDo you want to use the default AWS profile [default] and region [us-west-2]?", default=True
        )

    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("click.confirm")
    @patch("click.prompt")
    def test_get_aws_configuration_choice_selected(self, prompt_mock, confirm_mock, session_mock):
        confirm_mock.side_effect = [False]
        prompt_mock.side_effect = ["2", "us-east-2"]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "us-west-2"
        session_mock.return_value.available_profiles = ["default", "test-profile"]
        session_mock.return_value.get_available_regions.return_value = [
            "us-east-1",
            "us-east-2",
            "us-west-2",
            "eu-west-1",
            "ap-northeast-1",
        ]
        aws_configuration_choice = get_aws_configuration_choice()
        self.assertEqual(aws_configuration_choice["profile"], "test-profile")
        self.assertEqual(aws_configuration_choice["region"], "us-east-2")
        confirm_mock.assert_any_call(
            "\nDo you want to use the default AWS profile [default] and region [us-west-2]?", default=True
        )
        prompt_mock.assert_any_call("Profile", type=ANY, show_choices=False)
        prompt_mock.assert_any_call("Region [us-west-2]", type=ANY, show_choices=False)

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
    def test_get_aws_configuration_allow_free_text_region_value(self, prompt_mock, confirm_mock, session_mock):
        confirm_mock.side_effect = [False]
        prompt_mock.side_effect = ["2", "random-region"]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "us-west-2"
        session_mock.return_value.available_profiles = ["default", "test-profile"]
        session_mock.return_value.get_available_regions.return_value = [
            "us-east-1",
            "us-east-2",
            "us-west-2",
            "eu-west-1",
            "ap-northeast-1",
        ]
        aws_configuration_choice = get_aws_configuration_choice()
        self.assertEqual(aws_configuration_choice["profile"], "test-profile")
        self.assertEqual(aws_configuration_choice["region"], "random-region")
        confirm_mock.assert_any_call(
            "\nDo you want to use the default AWS profile [default] and region [us-west-2]?", default=True
        )
        prompt_mock.assert_any_call("Profile", type=ANY, show_choices=False)
        prompt_mock.assert_any_call("Region [us-west-2]", type=ANY, show_choices=False)

    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("click.confirm")
    @patch("click.prompt")
    def test_get_aws_configuration_succeeds_with_default(self, prompt_mock, confirm_mock, session_mock):
        region = "us-east-2"
        confirm_mock.side_effect = [True]
        prompt_mock.side_effect = ["1", region]

        def profile_mock(**kwargs):
            session = Mock()
            session.profile_name = "default"
            session.available_profiles = ["test-profile-1", "test-profile-2"]
            session.get_available_regions.return_value = [
                "us-east-1",
                "us-east-2",
                "us-west-2",
                "eu-west-1",
                "ap-northeast-1",
            ]
            if "profile_name" in kwargs:
                session.profile_name = kwargs["profile_name"]
                session.region_name = region
            else:
                session.profile_name = "default"
                session.region_name = None
            return session

        session_mock.side_effect = profile_mock

        aws_configuration_choice = get_aws_configuration_choice()
        self.assertEqual(aws_configuration_choice["profile"], "test-profile-1")
        self.assertEqual(aws_configuration_choice["region"], region)

        # Since the region will be None, the user should not get prompted to confirm
        # whether to choose a different profile.
        self.assertFalse(confirm_mock.called)

        prompt_mock.assert_any_call("Profile", type=ANY, show_choices=False)
        prompt_mock.assert_any_call(f"Region [{region}]", type=ANY, show_choices=False)
