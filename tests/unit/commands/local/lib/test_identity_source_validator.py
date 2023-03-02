from unittest import TestCase

from parameterized import parameterized

from samcli.commands.local.lib.validators.identity_source_validator import IdentitySourceValidator
from samcli.local.apigw.route import Route


class TestIdentitySourceValidator(TestCase):
    @parameterized.expand(
        [
            ("method.request.header.this-is_my.header", Route.API),
            ("method.request.querystring.this_is-my_query.string", Route.API),
            ("context.this.is.a_cool-context", Route.API),
            ("stageVariables.my.stage_vari-ble", Route.API),
            ("$request.header.this-is_my.header", Route.HTTP),
            ("$request.querystring.this_is-my_query.string", Route.HTTP),
            ("$context.this.is.a_cool-context", Route.HTTP),
            ("$stageVariables.my.stage_vari-ble", Route.HTTP),
        ]
    )
    def test_valid_identity_sources(self, identity_source, event_type):
        self.assertTrue(IdentitySourceValidator.validate_identity_source(identity_source, event_type))

    @parameterized.expand(
        [
            ("method.request.header.this+is+my~header", Route.API),
            ("method.request.querystring.this+is+my~query?string", Route.API),
            ("context.this?is~a_cool-context", Route.API),
            ("stageVariables.my][stage|vari-ble", Route.API),
            ("", Route.API),
            ("method.request.querystring", Route.API),
            ("method.request.header", Route.API),
            ("context", Route.API),
            ("stageVariable", Route.API),
            ("hello world", Route.API),
            ("$request.header.this+is+my~header", Route.HTTP),
            ("$request.querystring.this+is+my~query?string", Route.HTTP),
            ("$context.this?is~a_cool-context", Route.HTTP),
            ("$stageVariables.my][stage|vari-ble", Route.HTTP),
            ("", Route.HTTP),
            ("$request.querystring", Route.HTTP),
            ("$request.header", Route.HTTP),
            ("$context", Route.HTTP),
            ("$stageVariable", Route.HTTP),
            ("hello world", Route.HTTP),
        ]
    )
    def test_invalid_identity_sources(self, identity_source, event_type):
        self.assertFalse(IdentitySourceValidator.validate_identity_source(identity_source, event_type))
