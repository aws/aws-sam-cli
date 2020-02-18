import boto3
import logging

from unittest import TestCase
from unittest.mock import patch, ANY

from samcli.cli.context import Context


class TestContext(TestCase):
    def test_must_initialize_with_defaults(self):
        ctx = Context()

        self.assertEqual(ctx.debug, False, "debug must default to False")

    def test_must_set_get_debug_flag(self):
        ctx = Context()

        ctx.debug = True
        self.assertEqual(ctx.debug, True, "debug must be set to True")
        self.assertEqual(logging.getLogger("samcli").getEffectiveLevel(), logging.DEBUG)
        self.assertEqual(logging.getLogger("aws_lambda_builders").getEffectiveLevel(), logging.DEBUG)

    def test_must_unset_get_debug_flag(self):
        ctx = Context()

        ctx.debug = True
        self.assertEqual(ctx.debug, True, "debug must be set to True")

        # Flipping from True to False
        ctx.debug = False
        self.assertEqual(ctx.debug, False, "debug must be set to False")

    def test_must_set_aws_region_in_boto_session(self):
        region = "myregion"
        ctx = Context()

        ctx.region = region
        self.assertEqual(ctx.region, region)
        self.assertEqual(region, boto3._get_default_session().region_name)

    @patch("samcli.cli.context.boto3")
    def test_must_set_aws_profile_in_boto_session(self, boto_mock):
        profile = "foo"

        ctx = Context()

        ctx.profile = profile
        self.assertEqual(ctx.profile, profile)
        boto_mock.setup_default_session.assert_called_with(region_name=None, profile_name=profile, botocore_session=ANY)

    @patch("samcli.cli.context.boto3")
    def test_must_set_all_aws_session_properties(self, boto_mock):
        profile = "foo"
        region = "myregion"
        ctx = Context()

        ctx.profile = profile
        ctx.region = region
        boto_mock.setup_default_session.assert_called_with(
            region_name=region, profile_name=profile, botocore_session=ANY
        )

    @patch("samcli.cli.context.uuid")
    def test_must_set_session_id_to_uuid(self, uuid_mock):
        uuid_mock.uuid4.return_value = "abcd"
        ctx = Context()

        self.assertEqual(ctx.session_id, "abcd")

    @patch("samcli.cli.context.click")
    def test_must_find_context(self, click_mock):

        ctx = Context()
        result = ctx.get_current_context()

        self.assertEqual(click_mock.get_current_context.return_value.find_object.return_value, result)
        click_mock.get_current_context.return_value.find_object.assert_called_once_with(Context)

    @patch("samcli.cli.context.click")
    def test_create_new_context_if_not_found(self, click_mock):

        # Context can't be found
        click_mock.get_current_context.return_value.find_object.return_value = None

        ctx = Context()
        result = ctx.get_current_context()

        self.assertEqual(click_mock.get_current_context.return_value.ensure_object.return_value, result)
        click_mock.get_current_context.return_value.ensure_object.assert_called_once_with(Context)

    @patch("samcli.cli.context.click")
    def test_get_current_context_from_outside_of_click(self, click_mock):
        click_mock.get_current_context.return_value = None
        ctx = Context()

        # Context can't be found
        self.assertIsNone(ctx.get_current_context())
