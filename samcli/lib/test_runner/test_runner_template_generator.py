import re
import logging
import jinja2
import uuid
import os
from typing import Optional, List, Union
from samcli.commands.exceptions import TestRunnerTemplateGenerationException

LOG = logging.getLogger(__name__)


class FargateRunnerCFNTemplateGenerator:

    TEST_RUNNER_JINJA_FILE_NAME = "base_template.j2"
    TEST_RUNNER_JINJA_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), TEST_RUNNER_JINJA_FILE_NAME)

    def __init__(self, resource_arn_list: Optional[List[str]]):
        self.resource_arn_list = resource_arn_list

    def _get_jinja_template_string(self) -> str:
        """
        Returns the base jinja template string for the Test Runner CloudFormation Template
        """
        with open(self.TEST_RUNNER_JINJA_TEMPLATE_PATH) as test_runner_jinja_template:
            return test_runner_jinja_template.read()

    def _extract_api_id_from_arn(self, api_arn: str) -> str:
        """
        Extracts an api id from an HTTP or REST api arn.

        NOTE: https://docs.aws.amazon.com/apigateway/latest/developerguide/arn-format-reference.html

        REST API Arn: `arn:partition:apigateway:region::/restapis/api-id`

        HTTP API Arn: `arn:partition:apigateway:region::/apis/api-id`

        Parameters
        ----------
        api_arn : str
            The arn of the HTTP or REST api from which the api id is extracted.

        Returns
        -------
        str
            The api id from the api arn.
        """

        return api_arn[api_arn.rindex("/") + 1 :]

    def _create_iam_statement_string(self, resource_arn: str) -> Union[dict, None]:
        """
        Returns an IAM Statement in the form of a YAML string corresponding to the supplied resource ARN.

        The generated Actions are commented out to establish a barrier of consent, preventing customers from accidentally granting permissions that they did not mean to.

        The Action list is empty if there are no IAM Action permissions to generate for the given resource.

        Returns `None` if the `resource_arn` corresponds to an IAM or STS resource.

        Parameters
        ----------
        resource_arn : str
            The arn of the resource for which the IAM statement is generated.

        Returns
        -------
        str:
            An IAM Statement in the form of a YAML string.

            `None` if the `resource_arn` corresponds to an IAM or STS resource.

        Raises
        ------
        jinja2.exceptions.TemplateError:
            If the IAM Statement template render fails.
        """

        # We keep partition and region general to avoid the burden of maintaining new regions & partitions.
        partition_regex = r"[\w-]+"
        region_regex = r"[\w-]+"
        account_regex = r"\d{12}"

        # We want to explcitly avoid generating permissions for IAM or STS resources
        IAM_PREFIX_REGEX = rf"^arn:{partition_regex}:(iam|sts)"

        if re.search(IAM_PREFIX_REGEX, resource_arn):
            LOG.debug("ARN `%s` is for an IAM or STS resource, will not generate permissions.", resource_arn)
            return None

        LAMBDA_FUNCTION_REGEX = rf"^arn:{partition_regex}:lambda:{region_regex}:{account_regex}:function:[\w-]+(:\d+)?$"
        APIGW_API_REGEX = rf"^arn:{partition_regex}:apigateway:{region_regex}::\/apis\/\w+$"
        APIGW_RESTAPI_REGEX = rf"^arn:{partition_regex}:apigateway:{region_regex}::\/restapis\/\w+$"
        SQS_QUEUE_REGEX = rf"^arn:{partition_regex}:sqs:{region_regex}:{account_regex}:[\w-]+$"
        S3_BUCKET_REGEX = rf"^arn:{partition_regex}:s3:::[\w-]+$"
        DYNAMODB_TABLE_REGEX = rf"^arn:{partition_regex}:dynamodb:{region_regex}:{account_regex}:table\/[\w-]+$"
        STEPFUNCTION_REGEX = rf"^arn:{partition_regex}:states:{region_regex}:{account_regex}:stateMachine:[\w-]+$"

        default_permissions_map = {
            LAMBDA_FUNCTION_REGEX: ["lambda:InvokeFunction"],
            APIGW_API_REGEX: ["execute-api:Invoke"],
            APIGW_RESTAPI_REGEX: ["execute-api:Invoke"],
            SQS_QUEUE_REGEX: ["sqs:SendMessage"],
            S3_BUCKET_REGEX: ["s3:PutObject", "s3:GetObject"],
            DYNAMODB_TABLE_REGEX: [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
            ],
            STEPFUNCTION_REGEX: [
                "stepfunction:StartExecution",
                "stepfunction:StopExecution",
            ],
        }

        new_statement_template = (
            "- Effect: Allow\n"
            "  Action:\n"
            "   {%- for action in action_list %}\n"
            "     # - {{action}}\n"
            "   {%- endfor %}\n"
            "  Resource: {{arn}}\n"
        )

        for arn_regex, action_list in default_permissions_map.items():
            if re.search(arn_regex, resource_arn) is not None:
                LOG.debug("Matched ARN `%s` to IAM actions %s", resource_arn, action_list)

                # APIGW API IAM Statements:
                # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html
                if arn_regex in (APIGW_API_REGEX, APIGW_RESTAPI_REGEX):
                    apiId = self._extract_api_id_from_arn(resource_arn)
                    execute_api_arn = (
                        f"!Sub arn:${{AWS::Partition}}:execute-api:${{AWS::Region}}:${{AWS::AccountId}}:{apiId}/*"
                    )
                    return jinja2.Template(source=new_statement_template, keep_trailing_newline=True).render(
                        action_list=action_list, arn=execute_api_arn
                    )
                else:
                    return jinja2.Template(source=new_statement_template, keep_trailing_newline=True).render(
                        action_list=action_list, arn=resource_arn
                    )

        # If the supplied ARN is for a resource without any default actions supported
        LOG.debug("Found no match for ARN `%s` to any IAM actions.", resource_arn)
        return jinja2.Template(source=new_statement_template, keep_trailing_newline=True).render(
            action_list=[], arn=resource_arn
        )

    def _get_default_bucket_name(self) -> str:
        """
        Returns a guaranteed unique default S3 Bucket name
        """
        return "test-runner-bucket" + str(uuid.uuid4())

    def generate_test_runner_template_string(self, image_uri: str) -> Union[dict, None]:
        """
        Renders a base jinja template to create the Test Runner Stack.

        Parameters
        ---------

        image_uri : str
            The URI of the Image to be used by the Test Runner Fargate task definition.

        Returns
        -------
        dict
            The Test Runner CloudFormation template in the form of a YAML string.

        Raises
        ------
        TestRunnerTemplateGenerationException
            If the template generation process fails
        """

        default_bucket_name = self._get_default_bucket_name()
        try:
            jinja_base_template = self._get_jinja_template_string()
        except FileNotFoundError as jinja_template_not_found_ex:
            raise TestRunnerTemplateGenerationException(
                f"Failed to open jinja template, File Not Found."
            ) from jinja_template_not_found_ex

        if self.resource_arn_list:

            statements_list = []
            for arn in self.resource_arn_list:
                try:
                    statement = self._create_iam_statement_string(arn)
                except jinja2.exceptions.TemplateError as template_error:
                    raise TestRunnerTemplateGenerationException(
                        f"Failed to render jinja template for IAM statement: {template_error}"
                    ) from template_error
                if statement:
                    statements_list.append(statement)
            # Compile all the statements into a single string
            generated_statements = "".join(statements_list).rstrip()
            if generated_statements:
                data = {
                    "image_uri": image_uri,
                    "s3_bucket_name": default_bucket_name,
                    "generated_statements": generated_statements,
                }
            # Do not supply the generated_statements key if there are none generated
            else:
                data = {"image_uri": image_uri, "s3_bucket_name": default_bucket_name}
        else:
            data = {"image_uri": image_uri, "s3_bucket_name": default_bucket_name}
        try:
            return jinja2.Template(
                jinja_base_template, undefined=jinja2.StrictUndefined, trim_blocks=True, lstrip_blocks=True
            ).render(data)
        except jinja2.exceptions.TemplateError as template_error:
            raise TestRunnerTemplateGenerationException(
                f"Failed to render jinja template: {template_error}"
            ) from template_error
