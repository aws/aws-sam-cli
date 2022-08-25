"""
CLI command for the "test_runner run" command
"""
import logging
import sys
from collections import OrderedDict
from datetime import datetime
from typing import List, Optional

import click

from samcli.cli.main import pass_context
from samcli.commands._utils.custom_options.option_nargs import OptionNargs

from samcli.commands.exceptions import InvalidEnvironmentVariableException

LOG = logging.getLogger(__name__)

SHORT_HELP = "Run your testsuite on Fargate! Test results will automatically be downloaded after the run is complete."
HELP_TEXT = """
This command takes a Test Runner CloudFormation template, deploys it (updates if it already exists), and executes your testsuite on Fargate"
"""


def _get_unique_bucket_directory_name() -> str:
    """
    Creates a unqiue test-run directory name using a formatted ISO 8601 string.

    This directory is created at the top level of the S3 bucket (to store tests and results) if the customer does not specify a bucket path.

    E.g. test_run_2022_08_11T10_53_54
    """
    current_date = datetime.now().isoformat()
    # Remove the microsends, too long
    current_date = current_date[: current_date.index(".")]
    # Replace the dashes and colons with underscores for consistency
    current_date = current_date.replace("-", "_").replace(":", "_")

    return f"test_run_{current_date}"


@click.command("run", help=HELP_TEXT, short_help=SHORT_HELP)
@click.option(
    "--runner-stack-name",
    required=True,
    type=str,
    help="""
The name of the Test Runner Stack to use. 

If a Test Runner Stack with this name does not yet exist, a template must be provided with `--runner-template` so it can be created.

If a Test Runner Stack with this name does exist, and a template is provided, the Test Runner Stack will be updated to match the provided template.
""",
)
@click.option(
    "--runner-template",
    "runner_template_path",
    required=False,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="Your Test Runner CloudFormation Template.",
)
@click.option(
    "--env",
    "env_file",
    required=False,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="A YAML file specifying environment variables to send to the Test Runner Fargate instance.",
)
@click.option(
    "--options",
    "test_command_options",
    required=False,
    type=str,
    help="Options to pass to the test command, e.g. '--maxFail=2'",
)
@click.option(
    "--tests",
    "tests_path",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
    help="""
The file/directory containing the tests you wish to run. These tests will be compressed and uploaded to the S3 Bucket in order for the Fargate task to download and run them.
""",
)
@click.option(
    "--requirements",
    "requirements_file_path",
    required=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help="""
The Python Requirements file, commonly named `requirements.txt` containing the dependencies necessary to execute your tests. This requirements file will be uploaded to the S3 Bucket and downloaded by the Fargate task, which will install the dependencies.
""",
)
@click.option(
    "--bucket",
    "bucket_override",
    required=False,
    type=str,
    help="""
An override for the S3 bucket used to store your tests and results.

If used, ensure that you've given the Fargate container access to your bucket through the ContainerIAMRole in your Test Runner CloudFormation Template.
""",
)
@click.option(
    "--path-in-bucket",
    required=False,
    type=str,
    default=_get_unique_bucket_directory_name(),
    help=f"""
Specify the path within the S3 bucket where the tests, requirements, and results will be stored.

By default, a top level directory named test_run_<ISO 8601 date>/ is created and used.

For example, right now it would be {_get_unique_bucket_directory_name()}/
""",
)
@click.option(
    "--ecs-cluster",
    "ecs_cluster_override",
    required=False,
    type=str,
    help="An override for the ECS Cluster in which Fargate runs your tests.",
)
@click.option(
    "--subnets",
    "subnets_override",
    required=False,
    cls=OptionNargs,
    type=list,
    help="""
Specify a space separated list of subnets to use when starting the test-running task.
If not specified, the Test Runner will automatically use subnets associated with your account.

E.g. --subnets subnet-1 subnet-2
""",
)
@pass_context
def cli(
    ctx,
    runner_stack_name: str,
    runner_template_path: Optional[click.Path],
    env_file: Optional[click.Path],
    test_command_options: Optional[str],
    tests_path: click.Path,
    requirements_file_path: click.Path,
    bucket_override: Optional[str],
    path_in_bucket: Optional[str],
    ecs_cluster_override: Optional[str],
    subnets_override: Optional[List[str]],
) -> None:
    """
    `sam test_runner run` command entry point
    """

    do_cli(
        ctx,
        runner_stack_name=runner_stack_name,
        runner_template_path=runner_template_path,
        env_file=env_file,
        test_command_options=test_command_options,
        tests_path=tests_path,
        requirements_file_path=requirements_file_path,
        bucket_override=bucket_override,
        path_in_bucket=path_in_bucket,
        ecs_cluster_override=ecs_cluster_override,
        subnets_override=subnets_override,
    )


def do_cli(
    ctx,
    runner_stack_name: str,
    runner_template_path: Optional[click.Path],
    env_file: Optional[click.Path],
    test_command_options: Optional[str],
    tests_path: click.Path,
    requirements_file_path: click.Path,
    bucket_override: Optional[str],
    path_in_bucket: Optional[str],
    ecs_cluster_override: Optional[str],
    subnets_override: Optional[List[str]],
) -> None:
    """
    implementation of `sam test_runner run` command
    """

    from samcli.lib.test_runner.fargate_testsuite_runner import FargateTestsuiteRunner
    from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config
    from samcli.yamlhelper import parse_yaml_file

    other_env_vars = parse_yaml_file(env_file) if env_file else {}
    if type(other_env_vars) is not OrderedDict:
        # The parse_yaml_file function will 'successfully' parse a plain string, but that is not a dictionary.
        raise InvalidEnvironmentVariableException(f"Failed to parse YAML `{env_file}` into dictionary.")

    boto_client_provider = get_boto_client_provider_with_config(region=ctx.region, profile=ctx.profile)

    _validate_other_env_vars(other_env_vars, FargateTestsuiteRunner.RESERVED_ENV_VAR_NAMES)

    runner = FargateTestsuiteRunner(
        boto_client_provider=boto_client_provider,
        runner_stack_name=runner_stack_name,
        tests_path=tests_path,
        requirements_file_path=requirements_file_path,
        path_in_bucket=path_in_bucket,
        other_env_vars=other_env_vars,
        bucket_override=bucket_override,
        ecs_cluster_override=ecs_cluster_override,
        subnets_override=subnets_override,
        runner_template_path=runner_template_path,
        test_command_options=test_command_options,
    )

    exit_code = runner.do_testsuite()
    # If tests fail, return non-zero exit code
    sys.exit(exit_code)


def _validate_other_env_vars(other_env_vars: dict, reserved_var_names: List[str]) -> None:
    from samcli.commands.exceptions import InvalidEnvironmentVariableException, ReservedEnvironmentVariableException

    reserved_vars = []
    for key in other_env_vars.keys():
        if key in reserved_var_names:
            reserved_vars.append(key)

    if len(reserved_vars) > 0:
        raise ReservedEnvironmentVariableException(
            f"The following are reserved environment variables, ensure they are not present in your environment variables file: {reserved_vars}"
        )
    for key, value in other_env_vars.items():
        if not str.isidentifier(key):
            raise InvalidEnvironmentVariableException(f"'{key}' is not a valid environment variable name.")

        if not value:
            raise InvalidEnvironmentVariableException(
                f"Environment variable '{key}' has no value, ensure each key has a string, int, or float value."
            )

        if type(value) not in (str, int, float):
            raise InvalidEnvironmentVariableException(
                f"Environment variable '{key}' has value of type {type(key)}, ensure each key has a string, int, or float value."
            )
