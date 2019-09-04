from unittest import TestCase
from mock import Mock
from parameterized import parameterized

import samcli.yamlhelper as yamlhelper

from samcli.commands.validate.lib.sam_template_validator import SamTemplateValidator
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException


class TestValidate(TestCase):

    VALID_TEST_TEMPLATES = [
        ("tests/functional/commands/validate/lib/models/alexa_skill.yaml"),
        ("tests/functional/commands/validate/lib/models/alexa_skill_with_skill_id.yaml"),
        ("tests/functional/commands/validate/lib/models/all_policy_templates.yaml"),
        ("tests/functional/commands/validate/lib/models/api_cache.yaml"),
        ("tests/functional/commands/validate/lib/models/api_endpoint_configuration.yaml"),
        ("tests/functional/commands/validate/lib/models/api_request_model.yaml"),
        ("tests/functional/commands/validate/lib/models/api_request_model_openapi_3.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_access_log_setting.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_auth_all_maximum.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_auth_all_maximum_openapi_3.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_auth_all_minimum.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_auth_all_minimum_openapi.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_auth_and_conditions_all_max.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_auth_no_default.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_aws_iam_auth_overrides.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_binary_media_types.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_binary_media_types_definition_body.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_canary_setting.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_auth_no_preflight_auth.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_auth_preflight_auth.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_conditions_no_definitionbody.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_only_credentials_false.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_only_headers.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_only_maxage.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_only_methods.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_and_only_origins.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_no_definitionbody.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_cors_openapi_3.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_default_aws_iam_auth.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_gateway_responses.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_gateway_responses_all.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_gateway_responses_all_openapi_3.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_gateway_responses_implicit.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_gateway_responses_minimal.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_gateway_responses_string_status_code.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_method_aws_iam_auth.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_method_settings.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_minimum_compression_size.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_open_api_version.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_open_api_version_2.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_openapi_definition_body_no_flag.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_resource_refs.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_swagger_and_openapi_with_auth.yaml"),
        ("tests/functional/commands/validate/lib/models/api_with_xray_tracing.yaml"),
        ("tests/functional/commands/validate/lib/models/basic_function_with_tags.yaml"),
        ("tests/functional/commands/validate/lib/models/basic_layer.yaml"),
        ("tests/functional/commands/validate/lib/models/cloudwatch_logs_with_ref.yaml"),
        ("tests/functional/commands/validate/lib/models/cloudwatchevent.yaml"),
        ("tests/functional/commands/validate/lib/models/cloudwatchlog.yaml"),
        ("tests/functional/commands/validate/lib/models/depends_on.yaml"),
        ("tests/functional/commands/validate/lib/models/explicit_api.yaml"),
        ("tests/functional/commands/validate/lib/models/explicit_api_openapi_3.yaml"),
        ("tests/functional/commands/validate/lib/models/explicit_api_with_invalid_events_config.yaml"),
        ("tests/functional/commands/validate/lib/models/function_concurrency.yaml"),
        ("tests/functional/commands/validate/lib/models/function_event_conditions.yaml"),
        ("tests/functional/commands/validate/lib/models/function_managed_inline_policy.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_alias.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_alias_and_event_sources.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_alias_intrinsics.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_condition.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_custom_codedeploy_deployment_preference.yaml"),
        (
            "tests/functional/commands/validate/lib/models/function_with_custom_conditional_codedeploy_deployment_preference.yaml"
        ),
        ("tests/functional/commands/validate/lib/models/function_with_deployment_and_custom_role.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_deployment_no_service_role.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_deployment_preference.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_deployment_preference_all_parameters.yaml"),
        (
            "tests/functional/commands/validate/lib/models/function_with_deployment_preference_multiple_combinations.yaml"
        ),
        ("tests/functional/commands/validate/lib/models/function_with_disabled_deployment_preference.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_dlq.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_global_layers.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_kmskeyarn.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_layers.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_many_layers.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_permissions_boundary.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_policy_templates.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_resource_refs.yaml"),
        ("tests/functional/commands/validate/lib/models/function_with_sns_event_source_all_parameters.yaml"),
        ("tests/functional/commands/validate/lib/models/global_handle_path_level_parameter.yaml"),
        ("tests/functional/commands/validate/lib/models/globals_for_api.yaml"),
        ("tests/functional/commands/validate/lib/models/globals_for_function.yaml"),
        ("tests/functional/commands/validate/lib/models/globals_for_function_path.yaml"),
        ("tests/functional/commands/validate/lib/models/globals_for_simpletable.yaml"),
        ("tests/functional/commands/validate/lib/models/implicit_and_explicit_api_with_conditions.yaml"),
        ("tests/functional/commands/validate/lib/models/implicit_api.yaml"),
        ("tests/functional/commands/validate/lib/models/implicit_api_with_auth_and_conditions_max.yaml"),
        ("tests/functional/commands/validate/lib/models/implicit_api_with_many_conditions.yaml"),
        ("tests/functional/commands/validate/lib/models/implicit_api_with_serverless_rest_api_resource.yaml"),
        ("tests/functional/commands/validate/lib/models/intrinsic_functions.yaml"),
        ("tests/functional/commands/validate/lib/models/iot_rule.yaml"),
        ("tests/functional/commands/validate/lib/models/layers_all_properties.yaml"),
        ("tests/functional/commands/validate/lib/models/layers_with_intrinsics.yaml"),
        ("tests/functional/commands/validate/lib/models/no_implicit_api_with_serverless_rest_api_resource.yaml"),
        ("tests/functional/commands/validate/lib/models/s3.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_create_remove.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_existing_lambda_notification_configuration.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_existing_other_notification_configuration.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_filter.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_multiple_events_same_bucket.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_multiple_functions.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_with_condition.yaml"),
        ("tests/functional/commands/validate/lib/models/s3_with_dependsOn.yaml"),
        ("tests/functional/commands/validate/lib/models/simple_table_ref_parameter_intrinsic.yaml"),
        ("tests/functional/commands/validate/lib/models/simple_table_with_extra_tags.yaml"),
        ("tests/functional/commands/validate/lib/models/simple_table_with_table_name.yaml"),
        ("tests/functional/commands/validate/lib/models/simpletable.yaml"),
        ("tests/functional/commands/validate/lib/models/simpletable_with_sse.yaml"),
        ("tests/functional/commands/validate/lib/models/sns.yaml"),
        ("tests/functional/commands/validate/lib/models/sns_existing_other_subscription.yaml"),
        ("tests/functional/commands/validate/lib/models/sns_topic_outside_template.yaml"),
        ("tests/functional/commands/validate/lib/models/sqs.yaml"),
        ("tests/functional/commands/validate/lib/models/streams.yaml"),
        ("tests/functional/commands/validate/lib/models/unsupported_resources.yaml"),
    ]

    def test_valid_template(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "CodeUri": "s3://fake-bucket/lambda-code.zip",
                        "Runtime": "nodejs6.10",
                        "Timeout": 60,
                    },
                }
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()

    def test_invalid_template(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "CodeUri": "s3://lambda-code.zip", "Timeout": 60},
                }
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        with self.assertRaises(InvalidSamDocumentException):
            validator.is_valid()

    def test_valid_template_with_local_code_for_function(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {"Handler": "index.handler", "CodeUri": "./", "Runtime": "nodejs6.10", "Timeout": 60},
                }
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()

    def test_valid_template_with_local_code_for_layer_version(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessLayerVersion": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "./"}}
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()

    def test_valid_template_with_local_code_for_api(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {"StageName": "Prod", "DefinitionUri": "./"},
                }
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()

    def test_valid_template_with_DefinitionBody_for_api(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {"StageName": "Prod", "DefinitionBody": {"swagger": "2.0"}},
                }
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()

    def test_valid_template_with_s3_object_passed(self):
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "ServerlessApi": {
                    "Type": "AWS::Serverless::Api",
                    "Properties": {
                        "StageName": "Prod",
                        "DefinitionUri": {"Bucket": "mybucket-name", "Key": "swagger", "Version": 121212},
                    },
                },
                "ServerlessFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "CodeUri": {"Bucket": "mybucket-name", "Key": "code.zip", "Version": 121212},
                        "Runtime": "nodejs6.10",
                        "Timeout": 60,
                    },
                },
            },
        }

        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()

        # validate the CodeUri was not changed
        self.assertEquals(
            validator.sam_template.get("Resources").get("ServerlessApi").get("Properties").get("DefinitionUri"),
            {"Bucket": "mybucket-name", "Key": "swagger", "Version": 121212},
        )
        self.assertEquals(
            validator.sam_template.get("Resources").get("ServerlessFunction").get("Properties").get("CodeUri"),
            {"Bucket": "mybucket-name", "Key": "code.zip", "Version": 121212},
        )

    @parameterized.expand(VALID_TEST_TEMPLATES)
    def test_valid_api_request_model_template(self, template_path):
        with open(template_path) as f:
            template = yamlhelper.yaml_parse(f.read())
        managed_policy_mock = Mock()
        managed_policy_mock.load.return_value = {"PolicyName": "FakePolicy"}

        validator = SamTemplateValidator(template, managed_policy_mock)

        # Should not throw an exception
        validator.is_valid()
