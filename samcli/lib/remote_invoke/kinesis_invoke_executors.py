"""
Remote invoke executor implementation for Kinesis streams
"""

import logging
import uuid
from dataclasses import asdict, dataclass
from typing import cast

from botocore.exceptions import ClientError, ParamValidationError
from mypy_boto3_kinesis import KinesisClient

from samcli.lib.remote_invoke.exceptions import (
    ErrorBotoApiCallException,
    InvalidResourceBotoParameterException,
)
from samcli.lib.remote_invoke.remote_invoke_executors import (
    BotoActionExecutor,
    RemoteInvokeIterableResponseType,
    RemoteInvokeOutputFormat,
    RemoteInvokeResponse,
)

LOG = logging.getLogger(__name__)
STREAM_NAME = "StreamName"
DATA = "Data"
PARTITION_KEY = "PartitionKey"


@dataclass
class KinesisStreamPutRecordTextOutput:
    """
    Dataclass that stores put_record boto3 API fields used to create
    text output.
    """

    ShardId: str
    SequenceNumber: str

    def get_output_response_dict(self) -> dict:
        """
        Returns a dict of existing dataclass fields.

        Returns
        -------
        dict
            Returns the dict of the fields that will be used as the output response for
            text format output.
        """
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})


class KinesisPutDataExecutor(BotoActionExecutor):
    """
    Calls "put_record" method of "Kinesis stream" service with given input.
    If a file location provided, the file handle will be passed as input object.
    """

    _kinesis_client: KinesisClient
    _stream_name: str
    _remote_output_format: RemoteInvokeOutputFormat
    request_parameters: dict

    def __init__(self, kinesis_client: KinesisClient, physical_id: str, remote_output_format: RemoteInvokeOutputFormat):
        self._kinesis_client = kinesis_client
        self._remote_output_format = remote_output_format
        self._stream_name = physical_id
        self.request_parameters = {}

    def validate_action_parameters(self, parameters: dict) -> None:
        """
        Validates the input boto parameters and prepares the parameters for calling the API.

        Parameters
        ----------
        parameters: dict
            Boto parameters provided as input
        """
        for parameter_key, parameter_value in parameters.items():
            if parameter_key == STREAM_NAME:
                LOG.warning("StreamName is defined using the value provided for resource_id argument.")
            elif parameter_key == DATA:
                LOG.warning("Data is defined using the value provided for either --event or --event-file options.")
            else:
                self.request_parameters[parameter_key] = parameter_value

        if PARTITION_KEY not in self.request_parameters:
            self.request_parameters[PARTITION_KEY] = str(uuid.uuid4())

    def _execute_action(self, payload: str) -> RemoteInvokeIterableResponseType:
        """
        Calls "put_record" method to write single data record to Kinesis data stream.

        Parameters
        ----------
        payload: str
            The Data record which will be sent to the Kinesis stream

        Yields
        ------
        RemoteInvokeIterableResponseType
            Response that is consumed by remote invoke consumers after execution
        """
        if payload:
            self.request_parameters[DATA] = payload
        else:
            self.request_parameters[DATA] = "{}"
            LOG.debug("Input event not found, putting a record with Data {}")
        self.request_parameters[STREAM_NAME] = self._stream_name
        LOG.debug(
            "Calling kinesis_client.put_record with StreamName:%s, Data:%s",
            self.request_parameters[STREAM_NAME],
            self.request_parameters[DATA],
        )
        try:
            put_record_response = cast(dict, self._kinesis_client.put_record(**self.request_parameters))

            if self._remote_output_format == RemoteInvokeOutputFormat.JSON:
                yield RemoteInvokeResponse(put_record_response)
            if self._remote_output_format == RemoteInvokeOutputFormat.TEXT:
                put_record_text_output = KinesisStreamPutRecordTextOutput(
                    ShardId=put_record_response["ShardId"],
                    SequenceNumber=put_record_response["SequenceNumber"],
                )
                output_data = put_record_text_output.get_output_response_dict()
                yield RemoteInvokeResponse(output_data)
        except ParamValidationError as param_val_ex:
            raise InvalidResourceBotoParameterException(
                f"Invalid parameter key provided."
                f" {str(param_val_ex).replace(f'{STREAM_NAME}, ', '').replace(f'{DATA}, ', '')}"
            )
        except ClientError as client_ex:
            raise ErrorBotoApiCallException(client_ex) from client_ex
