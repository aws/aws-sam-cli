"""
Kicks off a testsuite in a Fargate container
"""
from typing import List
from samcli.commands.exceptions import ReservedEnvironmentVariableException


class SuiteRunner:
    def __init__(self, boto_ecs_client, boto_s3_client):
        self.boto_ecs_client = boto_ecs_client
        self.boto_s3_client = boto_s3_client

    def invoke_testsuite(
        self,
        bucket: str,
        path_in_bucket: str,
        ecs_cluster: str,
        container_name: str,
        task_definition_arn: str,
        other_env_vars: dict,
        test_command_options: str,
        subnets: List[str],
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
            If run_task fails

        botocore.WaiterError
            If the results.tar.gz fails to appear in the bucket
        """

        container_env_vars = {
            "TEST_RUNNER_BUCKET": bucket,
            "TEST_COMMAND_OPTIONS": test_command_options,
            "TEST_RUN_ID": path_in_bucket,
        }

        reserved_vars = []
        for key in other_env_vars.keys():
            if key in container_env_vars.keys():
                reserved_vars.append(key)
            if not str.isidentifier(key):
                raise ValueError(f"{key} is not a valid environment variable name.")

        if len(reserved_vars) > 0:
            raise ReservedEnvironmentVariableException(
                f"The following are reserved environment variable, ensure they are not present in your environment variables file: {reserved_vars}"
            )

        container_env_vars.update(other_env_vars)

        self.boto_ecs_client.run_task(
            cluster=ecs_cluster,
            launchType="FARGATE",
            networkConfiguration={"awsvpcConfiguration": {"subnets": subnets, "assignPublicIp": "ENABLED"}},
            overrides={
                "containerOverrides": [
                    {
                        "name": container_name,
                        "environment": [{"name": key, "value": val} for key, val in container_env_vars.items()],
                    }
                ]
            },
            taskDefinition=task_definition_arn,
        )

        results_upload_waiter = self.boto_s3_client.get_waiter("object_exists")
        results_upload_waiter.wait(Bucket=bucket, Key=path_in_bucket + "/results.tar.gz")
