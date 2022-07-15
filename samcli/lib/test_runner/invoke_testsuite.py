from typing import *
import click
from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.commands.exceptions import ReservedEnvironmentVariableException


def get_subnets(boto_client_provider: BotoProviderType) -> List[str]:
    """
    Queries describe-subnets to get subnets associated with the customer account.

    NOTE: https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeSubnets.html

    Parameters
    ----------
    boto_client_provider : BotoProviderType
        Provides a boto3 client in order to query the describe-subnets API

    Returns
    -------
    List[str]
        A list of subnet ids associated with a customer account.

    Raises
    ------
    botocore.ClientError
        If the describe_subnets call fails
    """
    ec2_client = boto_client_provider("ec2")
    subnets = ec2_client.describe_subnets().get("Subnets")
    return [subnet["SubnetId"] for subnet in subnets]


def invoke_testsuite(
    boto_client_provider: BotoProviderType,
    bucket: str,
    path_in_bucket: str,
    ecs_cluster: str,
    container_name: str,
    task_definition_arn: str,
    other_env_vars: dict,
    test_command_options: str,
    do_await: bool = False,
) -> None:

    """
    Kicks off a testsuite by making a runTask query.

    NOTE: https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html

    Parameters
    ----------
    boto_client_provider : BotoProviderType
        Provides a boto3 client in order to make a runTask query.

        Also used for waiting for results to appear in the s3 bucket.

    bucket : str
        The name of the bucket used to store results.

    path_in_bucket : str
        The path within the bucket where results are stored.

    ecs_cluster : str
        The name of the ECS Cluster to run the task on.

    container_name : str
        The name of the container in which the testsuite runs.

        This is required to specify environment variables in a containerOverride.

    task_definition_arn : str
        The ARN of the task definition to run.

    other_env_vars : dict
        Other environment variables to be sent to the container.

    test_command_options : str
        Options to be passed to the test command.

        For example, '--maxfail=2

    do_await : Optional[bool]
        If enabled, wait for the task to finish and for results to appear in the bucket.

    Raises
    ------
    botocore.ClientError
        If get_subnets, run_task, or waiters fail
    """

    # If the customer specifies their own subnet, use it, otherwise query describe-subnets.

    subnets = other_env_vars.get("subnets") or get_subnets(boto_client_provider)

    container_env_vars = [
        {"name": "BUCKET", "value": bucket},
        {"name": "TEST_RUN_ID", "value": path_in_bucket},
        {"name": "OPTIONS", "value": test_command_options},
    ]

    for key, value in other_env_vars.items():
        if key in ("BUCKET", "TEST_RUN_ID", "OPTIONS"):
            raise ReservedEnvironmentVariableException(
                f"{key} is a reserved environment variable, ensure that it is not present in your environment variables file."
            )

        container_env_vars.append({"name": key, "value": value})

    ecs_client = boto_client_provider("ecs")

    response = ecs_client.run_task(
        cluster=ecs_cluster,
        launchType="FARGATE",
        networkConfiguration={"awsvpcConfiguration": {"subnets": subnets, "assignPublicIp": "ENABLED"}},
        overrides={
            "containerOverrides": [
                {
                    "name": container_name,
                    "environment": container_env_vars,
                }
            ]
        },
        taskDefinition=task_definition_arn,
    )

    click.secho("Successfully kicked off testsuite!\n", fg="green")

    # If await is specified, wait for the task to finish and the results.tar.gz to appear in the bucket
    if do_await:
        click.secho("Awaiting testsuite completion...\n", fg="yellow")

        task_arn = response.get("tasks")[0].get("taskArn")
        task_waiter = ecs_client.get_waiter("tasks_running")

        s3_client = boto_client_provider("s3")

        results_upload_waiter = s3_client.get_waiter("object_exists")
        results_upload_waiter.wait(Bucket=bucket, Key=path_in_bucket + "/results.tar.gz")

        task_waiter.wait(cluster=ecs_cluster, tasks=[task_arn])
