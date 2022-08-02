"""
CLI command for "test-runner init" command
"""
from typing import Any, Optional
import logging

import click

from samcli.cli.main import pass_context
from samcli.commands.exceptions import NoResourcesMatchGivenTagException
from samcli.lib.test_runner.generate_env_vars import FargateRunnerArnMapGenerator
from samcli.lib.test_runner.test_runner_template_generator import FargateRunnerCFNTemplateGenerator
from samcli.lib.test_runner.utils import query_tagging_api, write_file
from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config
from samcli.lib.utils.colors import Colored

SHORT_HELP = "Generates a Test Runner CloudFormation Template in YAML format, as well as a resource-ARN map."
HELP_TEXT = """
This command generates a CloudFormation Template file that can be deployed to instantiate a Test Runner Stack.

It also generates a resource-ARN map, where the keys are your resource names in the format of an environment variable name, and the values
are the corresponding resource ARN. 

For example, 

_MY_LAMBDA_FUNCTION : arn:aws:lambda:us-east-1:123456789012:function:my-lambda-function

This resource-ARN map can be passed to the `sam test-runner run` command which will expose these mappings as environment variables to the Test Runner Fargate instance,
and thus can be used in test code.
"""

DEFAULT_RESOURCE_ARN_MAP_FILE_NAME = "test_runner_environment_variables.yaml"
DEFAULT_TEST_RUNNER_CFN_TEMPLATE_FILE_NAME = "test_runner_template.yaml"
SUPPORTED_RUNTIMES = ["python3.8"]

LOG = logging.getLogger(__name__)
COLOR = Colored()


@click.command("init", help=HELP_TEXT, short_help=SHORT_HELP)
@click.option(
    "--tag-key",
    type=str,
    required=False,
    help="""
Specify the key of the tag used to discover resources.

Discovered resources will have IAM statement templates generated within the Test Runner CloudFormation Template,
and a mapping between that resource name and its ARN included in the environment variable specification file.
""",
)
@click.option(
    "--tag-value",
    type=str,
    required=False,
    help="""
Specify the value of the tag used to discover resources.

Discovered resources will have IAM statement templates generated within the Test Runner CloudFormation Template,
and a mapping between that resource name and its ARN included in the environment variable specification file.
""",
)
@click.option(
    "--template-name",
    required=False,
    type=str,
    help="Specify the name of the generated Test Runner CloudFormation template.",
    default=DEFAULT_TEST_RUNNER_CFN_TEMPLATE_FILE_NAME,
)
@click.option(
    "--env-file",
    required=False,
    type=str,
    help="""
Specify the name of the generated resource-ARN map YAML file. This file can be passed to `sam test-runner run`, exposing the mappings as environment variables to the Fargate container.
""",
    default=DEFAULT_RESOURCE_ARN_MAP_FILE_NAME,
)
@click.option(
    "--runtime",
    required=False,
    type=click.Choice(SUPPORTED_RUNTIMES, case_sensitive=False),
    help=f"Specify the runtime with which to run tests.",
    default="python3.8",
)
@click.option(
    "--image-uri",
    required=True,
    type=str,
    help="THIS IS A TEMPORARY OPTION. Supply an image URI for Fargate to create a container to run tests.",
)
@pass_context
def cli(
    ctx: Any,
    tag_key: Optional[str],
    tag_value: Optional[str],
    template_name: str,
    env_file: str,
    runtime: str,
    image_uri: str,
) -> None:
    """
    `sam test-runner init` command entry point
    """

    do_cli(
        ctx=ctx,
        tag_key=tag_key,
        tag_value=tag_value,
        template_name=template_name,
        env_file=env_file,
        runtime=runtime,
        image_uri=image_uri,
    )


def do_cli(
    ctx: Any,
    tag_key: Optional[str],
    tag_value: Optional[str],
    template_name: str,
    env_file: str,
    runtime: str,
    image_uri: str,
) -> None:
    """
    implementation of the `sam test-runner init` command
    """

    # TODO: Merge these two options into one to follow AWS CLI (if we can get access to their parser)
    if tag_key and not tag_value:
        LOG.info(COLOR.red("Specified tag key without a tag value."))
        return

    if tag_value and not tag_key:
        LOG.info(COLOR.red("Specified tag value without a tag key."))
        return

    if tag_value and tag_key:
        tag_filters = [{"Key": tag_key, "Values": [tag_value]}]
    else:
        tag_filters = None

    # TODO: When ready, public ECR repositories will be created holding images capable of running tests for each available runtime.
    #       Until ready for public images, image URIs are supplied by option
    # image_uri = get_image_uri(runtime)

    if tag_filters is not None:
        boto_client_provider = get_boto_client_provider_with_config(region=ctx.region, profile=ctx.profile)
        resource_arn_list = query_tagging_api(tag_filters, boto_client_provider)

        if not resource_arn_list:
            raise NoResourcesMatchGivenTagException(
                f"Given tags `Key={tag_key},Value={tag_value}` do not match any resources, were they entered incorrectly?"
            )

        template_generator = FargateRunnerCFNTemplateGenerator(resource_arn_list)
        arn_map_generator = FargateRunnerArnMapGenerator()

        resource_arn_map_yaml_string = arn_map_generator.generate_env_vars_yaml_string(resource_arn_list)

        write_file(env_file, resource_arn_map_yaml_string)

        LOG.info(
            COLOR.green(
                f"✓ Sucessfully generated an environment variable specification file `test_runner_arn_map.yaml`.\n"
            )
        )
        LOG.info(
            COLOR.yellow(
                "These environment variables hold the ARNs of your testable resources, and passing this file to `sam test_runner run` will make them available in the container running your tests.\n\n"
                "Feel free to change them, or add new variables, but keep in mind that the test runner reserves the keys TEST_RUNNER_BUCKET, TEST_COMMAND_OPTIONS, and TEST_RUN_ID, and will throw an Exception if they are specified.\n\n"
                "If you add new resources or change existing ones, you can use `sam test-runner get-arns` to generate an updated environment variable specification file.\n"
            )
        )
    else:
        # If no tags were provided we cannot pass resource ARNs to the template generator to generate IAM statements
        # We also cannot generate a resource ARN map
        template_generator = FargateRunnerCFNTemplateGenerator([])

        LOG.info(
            COLOR.yellow(
                "No tags were provided, so a resource-ARN map was not created. You can still specify and send environment variables to the Fargate container running your tests by "
                "placing your desired NAME : VALUE pairs in a YAML file, and passing that YAML file to `sam test-runner run` with the --env option."
            )
        )
    test_runner_cfn_contents = template_generator.generate_test_runner_template_string(image_uri)
    write_file(template_name, test_runner_cfn_contents)

    LOG.info(
        COLOR.green(f"\n✓ Successfully generated a Test Runner CloudFormation Template named `{template_name}`!\n")
    )

    if tag_filters:
        # Only print this hint if the customer provided tags (and thus the corresponding resource ARN list)
        LOG.info(
            COLOR.yellow(
                "Make sure to enable any necessary auto generated IAM actions for your resources, by removing the `#` in front of the action. For example:\n\n"
                "         [DISABLED]                    [ENABLED]\n"
                "# - lambda:InvokeFunction  >>  - lambda:InvokeFunction\n\n"
                "Make any other changes you wish, and when you're ready to run your tests, use `sam test-runner run.`\n"
            )
        )
