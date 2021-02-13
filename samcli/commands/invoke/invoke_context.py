"""
Read and parse CLI args for the Invoke Command and setup the context for running the command
"""

import logging

import boto3
import botocore

from samcli.commands.exceptions import UserException
from samcli.lib.invoke.runner import InvokeRunner
from samcli.lib.utils import osutils
from samcli.lib.utils.stream_writer import StreamWriter

LOG = logging.getLogger(__name__)


class InvalidTimestampError(UserException):
    pass


class InvokeCommandContext:
    """
    Sets up a context to run the Invoke command by parsing the CLI arguments and creating necessary objects to be able
    to invoke the remote lambda

    This class **must** be used inside a ``with`` statement as follows:

        with InvokeCommandContext(**kwargs) as context:
            context.lambda_runner.invoke(...)
    """

    def __init__(
        self, function_name, stack_name, output_file=None
    ):
        """
        Initializes the context

        Parameters
        ----------
        function_name : str
            Name of the function to invoke

        stack_name : str
            Name of the stack where the function is available

        output_file : str
            Write function output to this file instead of Terminal
        """

        self._function_name = function_name
        self._stack_name = stack_name
        self._output_file = output_file
        self._output_file_handle = None

        self._lambda_client = boto3.client("lambda")
        self._cfn_client = boto3.client("cloudformation")

    def __enter__(self):
        """
        Performs some basic checks and returns itself when everything is ready to invoke a Lambda function.

        Returns
        -------
        InvokeCommandContext
            Returns this object
        """

        self._output_file_handle = self._setup_output_file(self._output_file)

        return self

    def __exit__(self, *args):
        """
        Cleanup any necessary opened files
        """

        if self._output_file_handle:
            self._output_file_handle.close()
            self._output_file_handle = None

    @property
    def lambda_runner(self):
        return InvokeRunner(self._lambda_client)

    @property
    def stdout(self):
        """
        Returns stream writer for stdout to output Lambda function logs to

        Returns
        -------
        samcli.lib.utils.stream_writer.StreamWriter
            Stream writer for stdout
        """
        stream = self._output_file_handle if self._output_file_handle else osutils.stdout()
        return StreamWriter(stream)

    @property
    def stderr(self):
        """
        Returns stream writer for stderr to output Lambda function errors to

        Returns
        -------
        samcli.lib.utils.stream_writer.StreamWriter
            Stream writer for stderr
        """
        stream = self._output_file_handle if self._output_file_handle else osutils.stderr()
        return StreamWriter(stream)

    @property
    def function_physical_id(self):
        """
        Physical ID of the AWS Lambda that we will be executing. It generates the name based on the
        Lambda Function name and stack name provided.

        Returns
        -------
        str
            Lambda Physical ID
        """

        function_id = self._get_resource_id_from_stack(self._cfn_client, self._stack_name, self._function_name)
        LOG.debug(
            "Function with LogicalId '%s' in stack '%s' resolves to actual physical ID '%s'",
            self._function_name,
            self._stack_name,
            function_id,
        )

        return function_id

    @property
    def output_file_handle(self):
        return self._output_file_handle

    @staticmethod
    def _setup_output_file(output_file):
        """
        Open a log file if necessary and return the file handle. This will create a file if it does not exist

        Parameters
        ----------
        output_file : str
            Path to a file where the logs should be written to

        Returns
        -------
        Handle to the opened log file, if necessary. None otherwise
        """
        if not output_file:
            return None

        return open(output_file, "wb")

    @staticmethod
    def _get_resource_id_from_stack(cfn_client, stack_name, logical_id):
        """
        Given the LogicalID of a resource, call AWS CloudFormation to get physical ID of the resource within
        the specified stack.

        Parameters
        ----------
        cfn_client
            CloudFormation client provided by AWS SDK

        stack_name : str
            Name of the stack to query

        logical_id : str
            LogicalId of the resource

        Returns
        -------
        str
            Physical ID of the resource

        Raises
        ------
        samcli.commands.exceptions.UserException
            If the stack or resource does not exist
        """

        LOG.debug(
            "Getting resource's PhysicalId from AWS CloudFormation stack. StackName=%s, LogicalId=%s",
            stack_name,
            logical_id,
        )

        try:
            response = cfn_client.describe_stack_resource(StackName=stack_name, LogicalResourceId=logical_id)

            LOG.debug("Response from AWS CloudFormation %s", response)
            return response["StackResourceDetail"]["PhysicalResourceId"]

        except botocore.exceptions.ClientError as ex:
            LOG.debug(
                "Unable to fetch resource name from CloudFormation Stack: "
                "StackName=%s, ResourceLogicalId=%s, Response=%s",
                stack_name,
                logical_id,
                ex.response,
            )

            # The exception message already has a well formatted error message that we can surface to user
            raise UserException(str(ex), wrapped_from=ex.response["Error"]["Code"]) from ex
