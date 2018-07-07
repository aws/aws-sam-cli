import boto3
import logging

from unittest import TestCase
from mock import patch

from samcli.cli.context import Context


class TestContext(TestCase):

    def test_must_initialize_with_defaults(self):
        ctx = Context()

        self.assertEquals(ctx.debug, False, "debug must default to False")

    def test_must_set_get_debug_flag(self):
        ctx = Context()

        ctx.debug = True
        self.assertEquals(ctx.debug, True, "debug must be set to True")
        self.assertEquals(logging.getLogger().getEffectiveLevel(), logging.DEBUG)

    def test_must_unset_get_debug_flag(self):
        ctx = Context()

        ctx.debug = True
        self.assertEquals(ctx.debug, True, "debug must be set to True")

        # Flipping from True to False
        ctx.debug = False
        self.assertEquals(ctx.debug, False, "debug must be set to False")

    def test_must_set_aws_region_in_boto_session(self):
        region = "myregion"
        ctx = Context()

        ctx.region = region
        self.assertEquals(ctx.region, region)
        self.assertEquals(region, boto3._get_default_session().region_name)

    @patch("samcli.cli.context.boto3")
    def test_must_set_aws_profile_in_boto_session(self, boto_mock):
        profile = "foo"

        ctx = Context()

        ctx.profile = profile
        self.assertEquals(ctx.profile, profile)
        boto_mock.setup_default_session.assert_called_with(region_name=None, profile_name=profile)

    @patch("samcli.cli.context.boto3")
    def test_must_set_all_aws_session_properties(self, boto_mock):
        profile = "foo"
        region = "myregion"
        ctx = Context()

        ctx.profile = profile
        ctx.region = region
        boto_mock.setup_default_session.assert_called_with(region_name=region, profile_name=profile)
