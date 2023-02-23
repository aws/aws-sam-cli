from unittest import TestCase
from parameterized import parameterized
from werkzeug.datastructures import Headers
from samcli.local.apigw.authorizers.lambda_authorizer import (
    ContextIdentitySource,
    HeaderIdentitySource,
    LambdaAuthorizer,
    QueryIdentitySource,
    StageVariableIdentitySource,
)


class TestHeaderIdentitySource(TestCase):
    def test_valid_header_identity_source(self):
        id_source = "test"
        header_id_source = HeaderIdentitySource(id_source)

        self.assertTrue(header_id_source.is_valid(**{"headers": Headers({id_source: 123})}))

    @parameterized.expand(
        [
            ({"headers": Headers({})}, "test"),  # test empty headers
            ({}, "test"),  # test no headers
            ({"headers": Headers({"not here": 123})}, "test"),  # test missing headers
        ]
    )
    def test_invalid_header_identity_source(self, sources_dict, id_source):
        header_id_source = HeaderIdentitySource(id_source)

        self.assertFalse(header_id_source.is_valid(**sources_dict))


class TestQueryIdentitySource(TestCase):
    @parameterized.expand(
        [
            ({"querystring": "foo=bar"}, "foo"),  # test single pair
            ({"querystring": "foo=bar&hello=world"}, "foo"),  # test single pair
        ]
    )
    def test_valid_query_identity_source(self, sources_dict, id_source):
        query_id_source = QueryIdentitySource(id_source)

        self.assertTrue(query_id_source.is_valid(**sources_dict))

    @parameterized.expand(
        [
            ({"querystring": ""}, "foo"),  # test empty string
            ({}, "foo"),  # test missing string
            ({"querystring": "hello=world"}, "foo"),  # test nonexistant pair
        ]
    )
    def test_invalid_query_identity_source(self, sources_dict, id_source):
        query_id_source = QueryIdentitySource(id_source)

        self.assertFalse(query_id_source.is_valid(**sources_dict))


class TestContextIdentitySource(TestCase):
    def test_valid_context_identity_source(self):
        id_source = "test"
        context_id_source = ContextIdentitySource(id_source)

        self.assertTrue(context_id_source.is_valid(**{"context": {id_source: 123}}))

    @parameterized.expand(
        [
            ({"context": {}}, "test"),  # test empty context
            ({}, "test"),  # test no context
            ({"headers": {"not here": 123}}, "test"),  # test missing context
        ]
    )
    def test_invalid_context_identity_source(self, sources_dict, id_source):
        context_id_source = ContextIdentitySource(id_source)

        self.assertFalse(context_id_source.is_valid(**sources_dict))


class TestStageVariableIdentitySource(TestCase):
    def test_valid_stage_identity_source(self):
        id_source = "test"
        stage_id_source = StageVariableIdentitySource(id_source)

        self.assertTrue(stage_id_source.is_valid(**{"stageVariables": {id_source: 123}}))

    @parameterized.expand(
        [
            ({"stageVariables": {}}, "test"),  # test empty stageVariables
            ({}, "test"),  # test no stageVariables
            ({"stageVariables": {"not here": 123}}, "test"),  # test missing stageVariables
        ]
    )
    def test_invalid_stage_identity_source(self, sources_dict, id_source):
        stage_id_source = StageVariableIdentitySource(id_source)

        self.assertFalse(stage_id_source.is_valid(**sources_dict))


class TestLambdaAuthorizer(TestCase):
    def test_parse_identity_sources(self):
        identity_sources = [
            "method.request.header.v1header",
            "$request.header.v2header",
            "method.request.querystring.v1query",
            "$request.querystring.v2query",
            "context.v1context",
            "$context.v2context",
            "stageVariables.v1stage",
            "$stageVariables.v2stage",
        ]

        expected_sources = [
            HeaderIdentitySource("v1header"),
            HeaderIdentitySource("v2header"),
            QueryIdentitySource("v1query"),
            QueryIdentitySource("v2query"),
            ContextIdentitySource("v1context"),
            ContextIdentitySource("v2context"),
            StageVariableIdentitySource("v1stage"),
            StageVariableIdentitySource("v2stage"),
        ]

        lambda_auth = LambdaAuthorizer(
            authorizer_name="auth_name",
            type="type",
            lambda_name="lambda_name",
            identity_sources=identity_sources,
            payload_version="version",
            validation_string="string",
            use_simple_response=True,
        )

        self.assertEqual(sorted(lambda_auth._identity_sources_raw), sorted(identity_sources))
        self.assertEqual(lambda_auth.identity_sources, expected_sources)
