"""
AWS Lambda clients for SAM CLI, including durable functions support.
"""

import logging
from typing import Any, Dict, List, Optional, Union

import botocore.session
from botocore.exceptions import ClientError

from samcli.local.lambdafn.exceptions import DurableExecutionNotFound

LOG = logging.getLogger(__name__)


class DurableFunctionsClient:
    """
    Client wrapper for AWS Lambda durable functions API calls.
    This is used for interacting with the durable functions emulator container.
    """

    def __init__(self, client):
        """
        Initialize the client.

        Args:
            client: Boto3 client for lambda service
        """
        self.client = client

    @classmethod
    def create(cls, host: str = "localhost", port: int = 5000, region: str = "us-west-2") -> "DurableFunctionsClient":
        """
        Create and initialize a lambda client to use with the durable executions emulator.

        The region argument is arbitrary since this method is only used to communicate with the emulator.
        The botocore client still requires a particular region, so we still pass one if the user doesn't
        have AWS_DEFAULT_REGION environment variable set.

        Args:
            host: Host of the durable functions emulator
            port: Port of the durable functions emulator
            region: AWS region for the client

        Returns:
            DurableFunctionsClient instance
        """
        endpoint_url = f"http://{host}:{port}"

        LOG.debug("Creating durable functions lambda client with endpoint: %s, region: %s", endpoint_url, region)

        try:
            # Create a fresh botocore session
            session = botocore.session.Session()

            # Create the boto3 client using the fresh session
            client = session.create_client(
                "lambda",
                endpoint_url=endpoint_url,
                region_name=region,
                # the emulator doesnt access any AWS resources,
                # but we need _some_ credentials to create a boto client
                aws_access_key_id="foo",
                aws_secret_access_key="bar",
            )

            return cls(client)
        except Exception as ex:
            # TODO: Determine appropriate exception type to raise for client creation failures
            raise Exception(f"Failed to create durable functions client: {str(ex)}")

    def send_callback_success(self, callback_id: str, result: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a success callback to a durable function execution.

        Args:
            callback_id: The callback ID to send response to
            result: Success result payload as string

        Returns:
            Dict containing the API response
        """

        # Prepare the request parameters
        params: Dict[str, Any] = {"CallbackId": callback_id}
        if result:
            # Convert string payload to bytes for the API
            params["Result"] = result.encode("utf-8")

        # Call the SendDurableExecutionCallbackSuccess API
        response: dict = self.client.send_durable_execution_callback_success(**params)
        response.pop("ResponseMetadata", None)
        return response

    def send_callback_failure(
        self,
        callback_id: str,
        error_data: Optional[str] = None,
        stack_trace: Optional[List[str]] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a failure callback to a durable function execution.

        Args:
            callback_id: The callback ID to send response to
            error_data: Additional error data
            stack_trace: Stack trace information as list of strings
            error_type: Type of error
            error_message: Detailed error message

        Returns:
            Dict containing the API response
        """

        # Prepare the error object according to the API schema
        error_object: Dict[str, Union[str, List[str]]] = {}
        if error_data:
            error_object["ErrorData"] = error_data
        if stack_trace:
            error_object["StackTrace"] = stack_trace
        if error_type:
            error_object["ErrorType"] = error_type
        if error_message:
            error_object["ErrorMessage"] = error_message

        # Prepare the request parameters
        params = {"CallbackId": callback_id, "Error": error_object}

        # Call the SendDurableExecutionCallbackFailure API
        response: dict = self.client.send_durable_execution_callback_failure(**params)
        response.pop("ResponseMetadata", None)
        return response

    def send_callback_heartbeat(self, callback_id: str) -> Dict[str, Any]:
        """
        Send a heartbeat callback to a durable function execution.

        Args:
            callback_id: The callback ID to send response to

        Returns:
            Dict containing the API response
        """

        # Prepare the request parameters (heartbeat only needs CallbackId)
        params = {"CallbackId": callback_id}

        # Call the SendDurableExecutionCallbackHeartbeat API
        response: dict = self.client.send_durable_execution_callback_heartbeat(**params)
        response.pop("ResponseMetadata", None)
        return response

    def get_durable_execution(self, durable_execution_arn: str) -> Dict[str, Any]:
        """
        Get details of a durable function execution.

        Args:
            durable_execution_arn: ARN of the durable execution to retrieve

        Returns:
            Dict containing execution details matching GetDurableExecution API response format
        """

        # Prepare the request parameters
        params = {"DurableExecutionArn": durable_execution_arn}

        try:
            # Call the GetDurableExecution API
            response: dict = self.client.get_durable_execution(**params)
            response.pop("ResponseMetadata", None)
            return response
        except ClientError as ex:
            if ex.response["Error"]["Code"] == "ResourceNotFoundException":
                raise DurableExecutionNotFound(f"Durable execution not found: {durable_execution_arn}")
            raise

    def get_durable_execution_history(
        self, durable_execution_arn: str, include_execution_data: bool = True
    ) -> Dict[str, Any]:
        """
        Get the execution history of a durable function execution.

        Args:
            durable_execution_arn: ARN of the durable execution to retrieve history for
            include_execution_data: Whether to include execution data in the response

        Returns:
            Dict containing execution history matching GetDurableExecutionHistory API response format
        """
        LOG.debug(
            "Getting durable execution history for ARN '%s' with include_execution_data=%s",
            durable_execution_arn,
            include_execution_data,
        )

        try:
            response: dict = self.client.get_durable_execution_history(
                DurableExecutionArn=durable_execution_arn, IncludeExecutionData=include_execution_data
            )
            response.pop("ResponseMetadata", None)
            return response
        except ClientError as ex:
            if ex.response["Error"]["Code"] == "ResourceNotFoundException":
                raise DurableExecutionNotFound(f"Durable execution not found: {durable_execution_arn}")
            raise

    def stop_durable_execution(
        self,
        durable_execution_arn: str,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        error_data: Optional[str] = None,
        stack_trace: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Stop a durable function execution.

        Args:
            durable_execution_arn: ARN of the durable execution to stop
            error_message: Optional error message
            error_type: Optional error type
            error_data: Optional error data
            stack_trace: Optional list of stack trace entries

        Returns:
            Dict containing the API response
        """
        LOG.debug("Stopping durable execution with ARN '%s'", durable_execution_arn)

        # Prepare the request parameters
        params: Dict[str, Any] = {"DurableExecutionArn": durable_execution_arn}

        # Add error object if any error fields are provided
        if error_message or error_type or error_data or stack_trace:
            error_object: Dict[str, Any] = {}
            if error_message:
                error_object["ErrorMessage"] = error_message
            if error_type:
                error_object["ErrorType"] = error_type
            if error_data:
                error_object["ErrorData"] = error_data
            if stack_trace:
                error_object["StackTrace"] = stack_trace
            params["Error"] = error_object

        try:
            # Call the StopDurableExecution API
            response: dict = self.client.stop_durable_execution(**params)
            response.pop("ResponseMetadata", None)
            return response
        except Exception:
            raise
