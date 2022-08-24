"""
Runs a testsuite in a Fargate container
"""
import logging
import os
import tarfile
import uuid
from pathlib import Path
from typing import List, Optional

from samcli.commands.deploy.exceptions import DeployFailedError
from samcli.commands.exceptions import MissingTestRunnerTemplateException, InvalidTestRunnerTemplateException
from samcli.lib.deploy.deployer import Deployer
from samcli.lib.utils.boto_utils import BotoProviderType
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.tar import create_tarball

LOG = logging.getLogger(__name__)


class FargateTestsuiteRunner:

    # Keep reserved names in one place so that we don't have to change info messages that inform customers of said reserved names
    RESERVED_ENV_VAR_NAMES = {"TEST_RUNNER_BUCKET", "TEST_COMMAND_OPTIONS", "TEST_RUN_DIR", "TEST_RUN_RESULTS_ID"}

    COMPRESSED_TESTS_FILE_NAME = "test.tar.gz"
    REQUIREMENTS_FILE_NAME = "requirements"
    COMPRESSED_RESULTS_FILE_NAME = f"results-{str(uuid.uuid4())}.tar.gz"
    RESULTS_STDOUT_FILE_NAME = "test_stdout.log"

    def __init__(
        self,
        boto_client_provider: BotoProviderType,
        runner_stack_name: str,
        tests_path: str,
        requirements_file_path: str,
        path_in_bucket: str,
        other_env_vars: dict,
        bucket_override: Optional[str],
        ecs_cluster_override: Optional[str],
        subnets_override: Optional[List[str]],
        runner_template_path: Optional[str],
        test_command_options: Optional[str],
        color=Colored(),
    ):

        self.boto_ecs_client = boto_client_provider("ecs")
        self.boto_ec2_client = boto_client_provider("ec2")
        self.boto_s3_client = boto_client_provider("s3")
        self.boto_cloudformation_client = boto_client_provider("cloudformation")

        self.runner_stack_name = runner_stack_name
        self.tests_path = Path(tests_path)
        self.requirements_file_path = Path(requirements_file_path)
        self.path_in_bucket = Path(path_in_bucket)
        self.bucket_override = bucket_override
        self.ecs_cluster_override = ecs_cluster_override
        self.subnets_override = subnets_override
        self.runner_template_path = Path(runner_template_path)
        self.other_env_vars = other_env_vars
        self.test_command_options = test_command_options

        self.color = color

        self.deployer = Deployer(cloudformation_client=self.boto_cloudformation_client)

    def _create_new_test_runner_stack(self, template_body: str) -> None:
        """
        Creates a new Test Runner stack using SAM Deployer, and displays log messages.

        Parameters
        ----------
        template_body : str
            The Test Runner CloudFormation Template to deploy
        """
        LOG.info(
            self.color.yellow(
                f"\n=> There does not exist a stack named '{self.runner_stack_name}', creating it from '{self.runner_template_path}'.\n"
            )
        )

        LOG.info(
            self.color.red(
                "! NOTE: The Test Runner Stack requires the creation of an IAM Role to allow Fargate to access the resources you wish to test against.\n\n"
                "! Stack creation will be done with CAPABILITY_IAM specified.\n"
            )
        )

        self.deployer.create_stack(
            StackName=self.runner_stack_name, TemplateBody=template_body, Capabilities=["CAPABILITY_IAM"]
        )
        self.deployer.wait_for_execute(
            stack_name=self.runner_stack_name, stack_operation="CREATE", disable_rollback=False
        )

    def _update_exisiting_test_runner_stack(self, template_body: str) -> None:
        """
        Updates an existing Test Runner Stack using the given template.

        If there are no updates to be performed, the update attempt is ignored and no exception is thrown.

        Parameters
        ----------
        template_body : str
            The Test Runner CloudFormation Template to deploy
        """
        LOG.info(
            self.color.yellow(
                f"\n=> A stack named '{self.runner_stack_name}' exists, updating it with '{self.runner_template_path}...'\n"
            )
        )

        LOG.info(
            self.color.red(
                "! NOTE: The Test Runner Stack requires the creation of an IAM Role to allow Fargate to access the resources you wish to test against.\n\n"
                "! Stack updating will be done with CAPABILITY_IAM specified.\n",
            )
        )
        try:
            self.deployer.update_stack(
                StackName=self.runner_stack_name, TemplateBody=template_body, Capabilities=["CAPABILITY_IAM"]
            )
            self.deployer.wait_for_execute(
                stack_name=self.runner_stack_name, stack_operation="UPDATE", disable_rollback=False
            )
        except DeployFailedError as deployment_exception:
            # If there is no update, just ignore it.
            if "No updates are to be performed" in str(deployment_exception):
                LOG.info(
                    self.color.yellow(
                        f"=> There are no updates to be performed on the stack '{self.runner_stack_name}', proceeding with testsuite execution...\n",
                    )
                )
            else:
                raise DeployFailedError(
                    stack_name=self.runner_stack_name, msg=str(deployment_exception)
                ) from deployment_exception

    def _update_or_create_test_runner_stack(self):
        """
        Creates a new Test Runner stack from a given template if a stack with the given name does not yet exist, or updates the existing Test Runner stack.

        Raises
        ------
        MissingTestRunnerTemplateException
            If the customer specifies a Test Runner stack name that does not exist, and also fails to provide a template to create it.
        """
        runner_stack_exists = self.deployer.has_stack(stack_name=self.runner_stack_name)

        if not runner_stack_exists:
            if not self.runner_template_path:
                raise MissingTestRunnerTemplateException(
                    f"There does not exist a stack named '{self.runner_stack_name}'. Please provide a Test Runner CloudFormation template with `--runner-template`, and the stack will be created.\n"
                    "To have a Test Runner CloudFormation template generated, run `sam test_runner init`.\n",
                )
            self._create_new_test_runner_stack(template_body=Path.read_text(self.runner_template_path))

        elif self.runner_template_path:
            self._update_exisiting_test_runner_stack(template_body=Path.read_text(self.runner_template_path))

    def _get_resource_list(self) -> List[dict]:
        """
        Returns a list of `StackResource` objects that compose the Test Runner Stack

        NOTE: `StackResource` definition: https://awscli.amazonaws.com/v2/documentation/api/latest/reference/cloudformation/describe-stack-resources.html#output
        """
        stack_information = self.boto_cloudformation_client.describe_stack_resources(StackName=self.runner_stack_name)
        resource_list = stack_information.get("StackResources")
        return resource_list

    def _get_unique_resource_physical_id(self, resource_list: List[dict], resource_type: str) -> str:
        """
        Extracts the physical ID of a resource with a given type from a given list of Test Runner `StackResources`

        An exception is thrown if there is no resource with the given type present in `resource_list` OR if there is more than one.

        This is because resources such as S3 Buckets and ECS Clusters are automatically picked up from the Test Runner Stack, and if there is more than one, the question of which to use is ambiguous.

        NOTE: `StackResource` definition: https://awscli.amazonaws.com/v2/documentation/api/latest/reference/cloudformation/describe-stack-resources.html#output

        Parameters
        ----------
        resource_list : List[dict]
            A list of `StackResource` objects

        resource_type : str
            The resource type to search for in the form `service-provider::service-name::data-type-name`. E.g. `AWS::S3::Bucket`

            NOTE: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html

        Raises
        ------
        InvalidTestRunnerTemplateException
            If the specified resource type exists more than once or not at all in `resource_list`
        """
        target_resources = [
            res.get("PhysicalResourceId") for res in resource_list if res.get("ResourceType") == resource_type
        ]

        if len(target_resources) > 1:
            raise InvalidTestRunnerTemplateException(
                f"The Test Runner Stack {self.runner_stack_name} contains more than one {resource_type}."
            )

        if not target_resources:
            raise InvalidTestRunnerTemplateException(
                f"The Test Runner Stack {self.runner_stack_name} does not contain a {resource_type}."
            )

        return target_resources[0]

    def _get_container_name(self, task_definition_arn: str) -> str:
        """
        Extracts the container name associated with the given TaskDefinition.

        Parameters
        ----------
        task_definition_arn : str
            The ARN of the TaskDefinition from which the container name is extracted.

        Returns
        -------
        str
            The container name associated with the given task definition ARN.
        """
        describe_task_definition_response = self.boto_ecs_client.describe_task_definition(
            taskDefinition=task_definition_arn
        )
        container_definitions = describe_task_definition_response.get("taskDefinition").get("containerDefinitions")

        if not container_definitions:
            raise InvalidTestRunnerTemplateException(
                f"The Test Runner Stack {self.runner_stack_name} task definition ({task_definition_arn}) does not contain a container definition."
            )

        if len(container_definitions) > 1:
            raise InvalidTestRunnerTemplateException(
                f"The Test Runner Stack {self.runner_stack_name} task definition ({task_definition_arn}) contains multiple container definitions."
            )

        container_name = container_definitions[0].get("name")
        return container_name

    def _get_subnets(self) -> List[str]:
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
        """
        subnets = self.boto_ec2_client.describe_subnets().get("Subnets")
        return [subnet["SubnetId"] for subnet in subnets]

    def _upload_tests_and_reqs(self, bucket: str) -> None:
        """
        Compress and upload tests and requirements to an S3 Bucket for the Fargate container to pick up.

        Parameters
        ----------
        bucket : str
            The bucket to which tests and requirements are uploaded.

            This is passed in because it is not known at the time of FargateTestsuiteRunner creation where the bucket name will come from.
            If a bucket override is not provided, the bucket contained in the Test Runner Stack must be used. The stack must be created/updated before this
            bucket can be fetched.
        """
        LOG.info(
            self.color.yellow(
                f"=> Compressing and uploading {self.tests_path} to {Path(bucket).joinpath(self.path_in_bucket).as_posix()}\n"
            )
        )

        # Compress tests into a temporary tarfile to send to S3 bucket
        # We set arcname to the stem of the tests_path to avoid including all the parent directories in the tarfile
        # E.g. If the customer specifies tests_path as a/b/c/tests, we want the tar to expand as tests, not a
        with create_tarball({self.tests_path: self.tests_path.stem}, mode="w:gz") as tests_tar:
            self.boto_s3_client.put_object(
                Body=tests_tar,
                Bucket=bucket,
                Key=self.path_in_bucket.joinpath(Path(self.COMPRESSED_TESTS_FILE_NAME)).as_posix(),
            )
        LOG.info(
            self.color.yellow(
                f"=> Uploading {self.requirements_file_path} to {Path(bucket).joinpath(self.path_in_bucket).as_posix()}\n"
            )
        )

        with open(self.requirements_file_path, "rb") as requirements_file:
            self.boto_s3_client.put_object(
                Body=requirements_file,
                Bucket=bucket,
                Key=self.path_in_bucket.joinpath(Path(self.REQUIREMENTS_FILE_NAME)).as_posix(),
            )

        waiter = self.boto_s3_client.get_waiter("object_exists")
        waiter.wait(Bucket=bucket, Key=self.path_in_bucket.joinpath(Path(self.COMPRESSED_TESTS_FILE_NAME)).as_posix())
        waiter.wait(Bucket=bucket, Key=self.path_in_bucket.joinpath(Path(self.REQUIREMENTS_FILE_NAME)).as_posix())

        LOG.info(self.color.green("✓ Tests and requirements sucessfully uploaded, kicking off testsuite...\n"))

    def _download_results(self, bucket: str) -> None:
        """
        Downloads test results from the bucket, as a tarball. The tarball is expanded, and removed after expansion.

        Parameters
        ----------
        bucket : str
            The bucket from which test results are downloaded.

            This is passed in because it is not known at the time of FargateTestsuiteRunner creation where the bucket name will come from.
            If a bucket override is not provided, the bucket contained in the Test Runner Stack must be used. The stack must be created/updated before this
            bucket can be fetched.
        """
        self.boto_s3_client.download_file(
            Bucket=bucket,
            Key=self.path_in_bucket.joinpath(self.COMPRESSED_RESULTS_FILE_NAME).as_posix(),
            Filename=self.COMPRESSED_RESULTS_FILE_NAME,
        )

        LOG.info(
            self.color.green(f"✓ Results sucessfully downloaded and saved into {self.COMPRESSED_RESULTS_FILE_NAME}  \n")
        )

        # The Fargate container packages all result files into a directory before tarring it,
        # so when the results are expanded, a single directory will be created,
        # and we will not have all the result files spilling into the current directory
        with tarfile.open(self.COMPRESSED_RESULTS_FILE_NAME) as results_tar:
            results_tar.extractall(".")

        # Remove the tarfile after extraction
        os.remove(self.COMPRESSED_RESULTS_FILE_NAME)

        LOG.info(
            self.color.green(
                f"✓ Expanded results into directory {self.path_in_bucket.stem}. Here is the test command standard output:\n"
            )
        )

        # The decompressed tarfile contents will be the basename of the path-in-bucket directory
        # E.g. Setting path-in-bucket to sample/path/run_01 => results will be in directory named run_01
        results_stdout_path = Path(self.path_in_bucket.stem).joinpath(self.RESULTS_STDOUT_FILE_NAME)
        results_stdout = Path.read_text(results_stdout_path)
        LOG.info(self.color.yellow(results_stdout))

    def _invoke_testsuite(
        self,
        bucket: str,
        ecs_cluster: str,
        container_name: str,
        task_definition_arn: str,
        subnets: List[str],
    ) -> None:

        """
        Kicks off a testsuite by making a runTask query.

        NOTE: https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html

        Parameters
        ----------
        bucket : str
            The name of the bucket used to store results.

        ecs_cluster : str
            The name of the ECS Cluster to run the task on.

        container_name : str
            The name of the container in which the testsuite runs.

            This is required to specify environment variables in a containerOverride.

        task_definition_arn : str
            The ARN of the task definition to run.

        Raises
        ------
        botocore.ClientError
            If run_task fails

        botocore.WaiterError
            If the results fails to appear in the bucket
        """

        container_env_vars = {
            "TEST_RUNNER_BUCKET": bucket,
            # Empty string default instead of None, runTask will not accept None
            "TEST_COMMAND_OPTIONS": self.test_command_options or "",
            "TEST_RUN_DIR": str(self.path_in_bucket),
            "TEST_RUN_RESULTS_ID": self.COMPRESSED_RESULTS_FILE_NAME,
        }

        container_env_vars.update(self.other_env_vars)

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

        LOG.info(self.color.yellow("=> Successfully kicked off testsuite, waiting for completion...\n"))

        results_upload_waiter = self.boto_s3_client.get_waiter("object_exists")
        results_upload_waiter.wait(
            Bucket=bucket, Key=self.path_in_bucket.joinpath(Path(self.COMPRESSED_RESULTS_FILE_NAME)).as_posix()
        )

        LOG.info(self.color.green("✓ Testsuite complete!\n"))

    def do_testsuite(self):
        """
        Runs a testsuite on Fargate.
        Tests and requirements are uploaded to an S3 bucket, which the Fargate container downlaods and runs.
        Results are uploaded to the same bucket, which the client downloads and prints to standard output.
        """

        self._update_or_create_test_runner_stack()

        resource_list = self._get_resource_list()

        task_definition_arn = self._get_unique_resource_physical_id(resource_list, "AWS::ECS::TaskDefinition")
        container_name = self._get_container_name(task_definition_arn)

        bucket = self.bucket_override or self._get_unique_resource_physical_id(resource_list, "AWS::S3::Bucket")
        ecs_cluster = self.ecs_cluster_override or self._get_unique_resource_physical_id(
            resource_list, "AWS::ECS::Cluster"
        )
        subnets = self.subnets_override or self._get_subnets()

        self._upload_tests_and_reqs(bucket)
        self._invoke_testsuite(
            bucket=bucket,
            ecs_cluster=ecs_cluster,
            container_name=container_name,
            task_definition_arn=task_definition_arn,
            subnets=subnets,
        )
        self._download_results(bucket)
