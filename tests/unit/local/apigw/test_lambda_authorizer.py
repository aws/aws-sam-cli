import json
from unittest import TestCase
from unittest.mock import Mock, patch
from parameterized import parameterized
from werkzeug.datastructures import Headers
from samcli.local.apigw.authorizers.lambda_authorizer import (
    ContextIdentitySource,
    HeaderIdentitySource,
    LambdaAuthorizer,
    LambdaAuthorizerIAMPolicyValidator,
    QueryIdentitySource,
    StageVariableIdentitySource,
)
from samcli.local.apigw.exceptions import InvalidLambdaAuthorizerResponse, InvalidSecurityDefinition


class TestHeaderIdentitySource(TestCase):
    def test_valid_header_identity_source(self):
        id_source = "test"
        header_id_source = HeaderIdentitySource(id_source)

        self.assertTrue(header_id_source.is_valid(**{"headers": Headers({id_source: 123})}))

    @parameterized.expand(
        [
            ({"headers": Headers({})},),  # test empty headers
            ({},),  # test no headers
            ({"headers": Headers({"not here": 123})},),  # type: ignore  # test missing headers
            ({"validation_expression": "^123$"},),  # test no headers, but provided validation
        ]
    )
    def test_invalid_header_identity_source(self, sources_dict):
        header_id_source = HeaderIdentitySource("test")

        self.assertFalse(header_id_source.is_valid(**sources_dict))

    def test_validation_expression_passes(self):
        id_source = "myheader"
        args = {"headers": Headers({id_source: "123"}), "validation_expression": "^123$"}

        header_id_source = HeaderIdentitySource(id_source)

        self.assertTrue(header_id_source.is_valid(**args))


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
        self.assertEqual(lambda_auth.identity_sources[0], expected_sources[0])

    def test_parse_invalid_identity_sources_raises(self):
        identity_sources = ["this is invalid"]

        with self.assertRaises(InvalidSecurityDefinition):
            LambdaAuthorizer(
                authorizer_name="auth_name",
                type="type",
                lambda_name="lambda_name",
                identity_sources=identity_sources,
                payload_version="version",
                validation_string="string",
                use_simple_response=True,
            )

    def test_response_validator_raises_exception(self):
        auth_name = "my auth"

        with self.assertRaises(InvalidLambdaAuthorizerResponse):
            LambdaAuthorizer(
                auth_name,
                Mock(),
                Mock(),
                [],
                Mock(),
                Mock(),
                Mock(),
            ).is_valid_response("not a valid json string", Mock())

    @patch.object(LambdaAuthorizer, "_validate_simple_response")
    @patch.object(LambdaAuthorizer, "_is_resource_authorized")
    def test_response_validator_calls_simple_response(self, resource_mock, simple_mock):
        LambdaAuthorizer(
            "my auth",
            Mock(),
            Mock(),
            [],
            LambdaAuthorizer.PAYLOAD_V2,
            Mock(),
            True,
        ).is_valid_response("{}", Mock())

        resource_mock.assert_not_called()
        simple_mock.assert_called_once()

    @parameterized.expand(
        [
            (  # authorizer v2, but not using simple response
                LambdaAuthorizer(
                    "my auth",
                    Mock(),
                    Mock(),
                    [],
                    LambdaAuthorizer.PAYLOAD_V2,
                    Mock(),
                    False,
                ),
            ),
            (  # authorizer v1
                LambdaAuthorizer(
                    "my auth",
                    Mock(),
                    Mock(),
                    [],
                    LambdaAuthorizer.PAYLOAD_V1,
                    Mock(),
                    False,
                ),
            ),
        ]
    )
    @patch.object(LambdaAuthorizer, "_validate_simple_response")
    @patch.object(LambdaAuthorizer, "_is_resource_authorized")
    @patch.object(LambdaAuthorizerIAMPolicyValidator, "validate_policy_document")
    @patch.object(LambdaAuthorizerIAMPolicyValidator, "validate_statement")
    def test_response_validator_calls_is_resource_authorized(
        self, validate_policy_mock, validate_statement_mock, lambda_auth, resource_mock, simple_mock
    ):
        LambdaAuthorizer(
            "my auth",
            Mock(),
            Mock(),
            [],
            LambdaAuthorizer.PAYLOAD_V1,
            Mock(),
            False,
        ).is_valid_response("{}", Mock())

        resource_mock.assert_called_once()
        simple_mock.assert_not_called()

    @parameterized.expand([({"missing": "key"},), ({"isAuthorized": "suppose to be bool"},)])
    def test_validate_simple_response_raises(self, input):
        with self.assertRaises(InvalidLambdaAuthorizerResponse):
            LambdaAuthorizer(
                "my auth",
                Mock(),
                Mock(),
                [],
                Mock(),
                Mock(),
                Mock(),
            )._validate_simple_response(input)

    def test_validate_simple_response(self):
        result = LambdaAuthorizer(
            "my auth",
            Mock(),
            Mock(),
            [],
            Mock(),
            Mock(),
            Mock(),
        )._validate_simple_response({"isAuthorized": True})

        self.assertTrue(result)

    def test_get_context(self):
        context = {"key": "value"}
        principal_id = "123"

        input = {"context": context, "principalId": principal_id}

        expected = context.copy()
        expected["principalId"] = principal_id

        result = LambdaAuthorizer(Mock(), Mock(), Mock(), [], Mock()).get_context(json.dumps(input))

        self.assertEqual(result, expected)

    @parameterized.expand(
        [
            (json.dumps([]),),
            ("not valid json",),
            (json.dumps({"context": "not dict"}),),
        ]
    )
    def test_get_context_raises_exception(self, input):
        with self.assertRaises(InvalidLambdaAuthorizerResponse):
            LambdaAuthorizer("myauth", Mock(), Mock(), [], Mock()).get_context(json.dumps(input))

    @parameterized.expand(
        [
            (  # deny effect
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [{"Action": "execute-api:Invoke", "Effect": "Deny", "Resource": [""]}]
                    },
                },
                False,
            ),
            (  # wrong action
                {
                    "principalId": "123",
                    "policyDocument": {"Statement": [{"Action": "hello world", "Effect": "Deny", "Resource": [""]}]},
                },
                False,
            ),
            (  # missing arn resource match
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [{"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": ["not the arn"]}]
                    },
                },
                False,
            ),
            (  # match wildcard same part
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": ["arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/hel*"],
                            }
                        ]
                    },
                },
                True,
            ),
            (  # match wildcard any
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": ["arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/*"],
                            }
                        ]
                    },
                },
                True,
            ),
            (  # match wildcard any path, any method
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": ["arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/*/*"],
                            }
                        ]
                    },
                },
                True,
            ),
            (  # fail match wildcard second part
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": ["arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/hello/*"],
                            }
                        ]
                    },
                },
                False,
            ),
            (  # fail match single random character
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": ["arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/he?lo"],
                            }
                        ]
                    },
                },
                True,
            ),
            (  # resource as string
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": "arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/hello",
                            }
                        ]
                    },
                },
                True,
            ),
            (  # action as list
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [
                            {
                                "Action": ["execute-api:Invoke"],
                                "Effect": "Allow",
                                "Resource": "arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/hello",
                            }
                        ]
                    },
                },
                True,
            ),
        ]
    )
    def test_validate_is_resource_authorized(self, response, expected_result):
        method_arn = "arn:aws:execute-api:us-east-1:123456789012:1234567890/prod/GET/hello"

        auth = LambdaAuthorizer(
            "my auth",
            Mock(),
            Mock(),
            [],
            Mock(),
            Mock(),
            Mock(),
        )

        result = auth._is_resource_authorized(response, method_arn)

        self.assertEqual(result, expected_result)


class TestLambdaAuthorizerIamPolicyValidator(TestCase):
    @parameterized.expand(
        [
            (  # missing principalId
                {},
                "Authorizer 'my auth' contains an invalid or missing 'principalId' from response",
            ),
            (  # missing policyDocument
                {"principalId": "123"},
                "Authorizer 'my auth' contains an invalid or missing 'policyDocument' from response",
            ),
            (  # policyDocument not dict
                {"principalId": "123", "policyDocument": "not list"},
                "Authorizer 'my auth' contains an invalid or missing 'policyDocument' from response",
            ),
        ]
    )
    def test_validate_validate_policy_document_raises(self, response, message):
        with self.assertRaisesRegex(InvalidLambdaAuthorizerResponse, message):
            LambdaAuthorizerIAMPolicyValidator.validate_policy_document("my auth", response)

    @parameterized.expand(
        [
            (  # policyDocument empty
                {"principalId": "123", "policyDocument": {}},
                "Authorizer 'my auth' contains an invalid or missing 'Statement' from response",
            ),
            (  # missing statement
                {"principalId": "123", "policyDocument": {"missing": "statement"}},
                "Authorizer 'my auth' contains an invalid or missing 'Statement'",
            ),
            (  # statement not list
                {"principalId": "123", "policyDocument": {"Statement": "statement"}},
                "Authorizer 'my auth' contains an invalid or missing 'Statement'",
            ),
            (  # statement empty
                {"principalId": "123", "policyDocument": {"Statement": []}},
                "Authorizer 'my auth' contains an invalid or missing 'Statement'",
            ),
            (  # statement not an object
                {"principalId": "123", "policyDocument": {"Statement": ["string"]}},
                "Authorizer 'my auth' policy document must be a list of object",
            ),
            (  # statement missing action
                {"principalId": "123", "policyDocument": {"Statement": [{"no action": "123"}]}},
                "Authorizer 'my auth' policy document contains an invalid 'Action'",
            ),
            (  # statement missing effect
                {"principalId": "123", "policyDocument": {"Statement": [{"Action": "execute-api:Invoke"}]}},
                "Authorizer 'my auth' policy document contains an invalid 'Effect'",
            ),
        ]
    )
    def test_validate_validate_statement_raises(self, response, message):
        with self.assertRaisesRegex(InvalidLambdaAuthorizerResponse, message):
            LambdaAuthorizerIAMPolicyValidator.validate_statement("my auth", response)

    @parameterized.expand(
        [
            (  # default
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [{"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": ["arn"]}]
                    },
                },
            ),
            (  # statement resource as string
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [{"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": "arn"}]
                    },
                },
            ),
            (  # statement action as list
                {
                    "principalId": "123",
                    "policyDocument": {
                        "Statement": [{"Action": ["execute-api:Invoke"], "Effect": "Allow", "Resource": ["arn"]}]
                    },
                },
            ),
        ]
    )
    def test_validate_validate_statement_does_not_raise(self, response):
        try:
            LambdaAuthorizerIAMPolicyValidator.validate_statement("my auth", response)
        except InvalidLambdaAuthorizerResponse as e:
            self.fail(f"validate statement raised unexpectedly: {e.message}")
