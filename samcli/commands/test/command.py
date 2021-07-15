"""CLI command for "test" command."""
import logging
import sys
from io import TextIOWrapper
from typing import cast

import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.context import Context
from samcli.cli.main import print_cmdline_args, pass_context, aws_creds_options, common_options
from samcli.lib.cli_validation.payload_file_validation import payload_and_payload_file_options_validation
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version

LOG = logging.getLogger(__name__)

HELP_TEXT = """
Invoke or send test data to remote resources in your CFN stack
"""
SHORT_HELP = "Test a deployed resource"


@click.command("test", help=HELP_TEXT, short_help=SHORT_HELP)
@configuration_option(provider=TomlProvider(section="parameters"))
@click.option("--stack-name", required=True, help="Name of the stack to get the resource information from")
@click.option("--resource-id", required=True, help="Name of the resource that will be tested")
@click.option(
    "--payload",
    help="The payload that will be sent to the resource. The target parameter will depend on the resource type. "
    "For instance: 'Payload' for Lambda, 'Entries' for SQS and 'Records' for Kinesis.",
)
@click.option(
    "--payload-file",
    type=click.File("r", encoding="utf-8"),
    help="The file that contains the payload that will be sent to the resource",
)
@click.option(
    "--tail",
    is_flag=True,
    help="Use this option to start tailing logs and XRay information for the given resource. "
    "The execution will continue until it is explicitly interrupted with Ctrl + C",
)
@payload_and_payload_file_options_validation
@common_options
@aws_creds_options
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx: Context,
    stack_name: str,
    resource_id: str,
    payload: str,
    payload_file: TextIOWrapper,
    tail: bool,
    config_file: str,
    config_env: str,
) -> None:
    """
    `sam test` command entry point
    """

    do_cli(stack_name, resource_id, payload, payload_file, tail, ctx.region, ctx.profile, config_file, config_env)


def do_cli(
    stack_name: str,
    resource_id: str,
    payload: str,
    payload_file: TextIOWrapper,
    tail: bool,
    region: str,
    profile: str,
    config_file: str,
    config_env: str,
) -> None:
    """
    Implementation of the ``cli`` method
    """
    from samcli.lib.test.test_executor_factory import TestExecutorFactory
    from samcli.lib.test.test_executors import TestExecutionInfo
    from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config, get_boto_resource_provider_with_config
    from samcli.lib.utils.cloudformation import get_resource_summary
    from samcli.commands.logs.logs_context import ResourcePhysicalIdResolver
    from samcli.commands.logs.puller_factory import generate_puller

    from datetime import datetime

    # create clients and required
    boto_client_provider = get_boto_client_provider_with_config(region_name=region)
    boto_resource_provider = get_boto_resource_provider_with_config(region_name=region)

    # get resource summary
    resource_summary = get_resource_summary(boto_resource_provider, stack_name, resource_id)
    if not resource_summary:
        LOG.error("Can't find the resource %s in given stack %s", resource_id, stack_name)
        return

    # generate executor with given resource
    test_executor_factory = TestExecutorFactory(boto_client_provider)
    test_executor = test_executor_factory.create_test_executor(resource_summary)

    if not test_executor:
        LOG.error("Resource (%s) is not supported with 'sam test' command", resource_id)
        return

    # set start_time for pulling logs later
    start_time = datetime.utcnow()

    # if no payload nor payload_file argument is given, read from stdin
    if not payload and not payload_file:
        LOG.info("Neither --payload nor --payload-file option have been provided, reading from stdin")
        payload_file = cast(TextIOWrapper, sys.stdin)

    test_exec_info = TestExecutionInfo(payload, payload_file)

    # run execution
    test_result = test_executor.execute(test_exec_info)

    if test_result.is_succeeded():
        LOG.info("Test succeeded, result: %s", test_result.response)

        if tail:
            LOG.debug("Tailing is enabled, generating puller instance to start tailing")
            resource_logical_id_resolver = ResourcePhysicalIdResolver(boto_resource_provider, stack_name, [])
            log_trace_puller = generate_puller(
                boto_client_provider, resource_logical_id_resolver.get_resource_information(), include_tracing=True
            )
            LOG.debug("Starting to pull logs and XRay traces, press Ctrl + C to stop it")
            log_trace_puller.tail(start_time)

    else:
        LOG.error("Test execution failed with following error", exc_info=test_result.exception)
