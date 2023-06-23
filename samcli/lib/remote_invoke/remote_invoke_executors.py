"""
Abstract class definitions and generic implementations for remote invoke
"""
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Callable, Generic, Iterable, List, Optional, TypeVar, Union, cast

from typing_extensions import TypeAlias

LOG = logging.getLogger(__name__)


@dataclass
class RemoteInvokeResponse:
    """
    Dataclass that contains response object of the remote invoke execution.
    dict for raw events, str for other ones
    """

    response: Union[str, dict]


@dataclass
class RemoteInvokeLogOutput:
    """
    Dataclass that contains log objects of the remote invoke execution
    """

    log_output: str


# type alias to keep consistency between different places for remote invoke return type
RemoteInvokeIterableResponseType: TypeAlias = Iterable[Union[RemoteInvokeResponse, RemoteInvokeLogOutput]]


class RemoteInvokeOutputFormat(Enum):
    """
    Types of output formats used to by remote invoke
    """

    TEXT = "text"
    JSON = "json"


class RemoteInvokeExecutionInfo:
    """
    Keeps request and response information about remote invoke execution

    payload: payload string given by the customer
    payload_file: if file is given, this points to its location

    response: response object returned from boto3 action
    exception: if an exception is thrown, it will be stored here
    """

    # Request related properties
    payload: Optional[Union[str, List, dict]]
    payload_file: Optional[TextIOWrapper]
    parameters: dict
    output_format: RemoteInvokeOutputFormat

    # Response related properties
    response: Optional[Union[dict, str]]
    log_output: Optional[str]
    exception: Optional[Exception]

    def __init__(
        self,
        payload: Optional[Union[str, List, dict]],
        payload_file: Optional[TextIOWrapper],
        parameters: dict,
        output_format: RemoteInvokeOutputFormat,
    ):
        self.payload = payload
        self.payload_file = payload_file
        self.parameters = parameters
        self.output_format = output_format
        self.response = None
        self.log_output = None
        self.exception = None

    def is_file_provided(self) -> bool:
        return bool(self.payload_file)

    @property
    def payload_file_path(self) -> Optional[TextIOWrapper]:
        return self.payload_file if self.is_file_provided() else None

    def is_succeeded(self) -> bool:
        return bool(self.response)


RemoteInvokeResponseType = TypeVar("RemoteInvokeResponseType")


class RemoteInvokeRequestResponseMapper(Generic[RemoteInvokeResponseType]):
    """
    Mapper definition which can be used map remote invoke requests or responses.

    For instance, if a string provided where JSON is required, a mapper can convert given string
    into JSON object for request.

    Or for a response object, if it contains streaming results, a mapper can convert them back
    to string to display on
    """

    @abstractmethod
    def map(self, remote_invoke_input: RemoteInvokeResponseType) -> RemoteInvokeResponseType:
        raise NotImplementedError()


class RemoteInvokeConsumer(Generic[RemoteInvokeResponseType]):
    @abstractmethod
    def consume(self, remote_invoke_response: RemoteInvokeResponseType) -> None:
        raise NotImplementedError()


class ResponseObjectToJsonStringMapper(RemoteInvokeRequestResponseMapper):
    """
    Maps response object inside RemoteInvokeExecutionInfo into formatted JSON string with multiple lines
    """

    def map(self, remote_invoke_input: RemoteInvokeResponse) -> RemoteInvokeResponse:
        LOG.debug("Converting response object into JSON")
        remote_invoke_input.response = json.dumps(remote_invoke_input.response, indent=2)
        return remote_invoke_input


class BotoActionExecutor(ABC):
    """
    Executes a specific boto3 service action and updates the response of the RemoteInvokeExecutionInfo object
    If execution throws an exception, it updates the exception information as well
    """

    @abstractmethod
    def _execute_action(self, payload: str) -> RemoteInvokeIterableResponseType:
        """
        Specific boto3 API call implementation.

        Parameters
        ----------
        payload : str
            Payload object that is been provided

        Returns
        -------
            Response dictionary from the API call

        """
        raise NotImplementedError()

    @abstractmethod
    def validate_action_parameters(self, parameters: dict):
        """
        Validates the input boto3 parameters before calling the API

        :param parameters: Boto parameters passed as input
        """
        raise NotImplementedError()

    def _execute_action_file(self, payload_file: TextIOWrapper) -> RemoteInvokeIterableResponseType:
        """
        Different implementation which is specific to a file path. Some boto3 APIs may accept a file path
        rather than a string. This implementation targets these options to support different file types
        other than just string.

        Default implementation reads the file contents as string and calls execute_action.

        Parameters
        ----------
        payload_file : Path
            Location of the payload file

        Returns
        -------
            Response dictionary from the API call
        """
        return self._execute_action(payload_file.read())

    def execute(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeIterableResponseType:
        """
        Executes boto3 API and updates response or exception object depending on the result

        Parameters
        ----------
        remote_invoke_input : RemoteInvokeExecutionInfo
            Remote execution details which contains payload or payload file information

        Returns
        -------
        RemoteInvokeIterableResponseType
            Returns iterable response, see response type definition for details
        """
        action_executor: Callable[[Any], Iterable[Union[RemoteInvokeResponse, RemoteInvokeLogOutput]]]
        payload: Union[str, Path]

        # if a file pointed is provided for payload, use specific payload and its function here
        if remote_invoke_input.is_file_provided():
            action_executor = self._execute_action_file
            payload = cast(Path, remote_invoke_input.payload_file_path)
        else:
            action_executor = self._execute_action
            payload = cast(str, remote_invoke_input.payload)

        # execute boto3 API, and update result if it is successful, update exception otherwise
        return action_executor(payload)


class RemoteInvokeExecutor:
    """
    Generic RemoteInvokeExecutor, which contains request mappers, response mappers and boto action executor.

    Input is been updated with the given list of request mappers.
    Then updated input have been passed to boto action executor to actually call the API
    Once the result is returned, if it is successful, response have been mapped with list of response mappers
    """

    _request_mappers: List[RemoteInvokeRequestResponseMapper[RemoteInvokeExecutionInfo]]
    _response_mappers: List[RemoteInvokeRequestResponseMapper[RemoteInvokeResponse]]
    _boto_action_executor: BotoActionExecutor

    _response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse]
    _log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput]

    def __init__(
        self,
        request_mappers: List[RemoteInvokeRequestResponseMapper[RemoteInvokeExecutionInfo]],
        response_mappers: List[RemoteInvokeRequestResponseMapper[RemoteInvokeResponse]],
        boto_action_executor: BotoActionExecutor,
        response_consumer: RemoteInvokeConsumer[RemoteInvokeResponse],
        log_consumer: RemoteInvokeConsumer[RemoteInvokeLogOutput],
    ):
        self._request_mappers = request_mappers
        self._response_mappers = response_mappers
        self._boto_action_executor = boto_action_executor
        self._response_consumer = response_consumer
        self._log_consumer = log_consumer

    def execute(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> None:
        """
        First runs all mappers for request object to get the final version of it.
        Then validates all the input boto parameters and invokes the BotoActionExecutor to get the result
        And finally, runs all mappers for the response object to get the final form of it.
        """
        remote_invoke_input = self._map_input(remote_invoke_input)
        self._boto_action_executor.validate_action_parameters(remote_invoke_input.parameters)
        for remote_invoke_result in self._boto_action_executor.execute(remote_invoke_input):
            if isinstance(remote_invoke_result, RemoteInvokeResponse):
                self._response_consumer.consume(self._map_output(remote_invoke_result))
            if isinstance(remote_invoke_result, RemoteInvokeLogOutput):
                self._log_consumer.consume(remote_invoke_result)

    def _map_input(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        """
        Maps the given input through the request mapper list.

        Parameters
        ----------
        remote_invoke_input : RemoteInvokeExecutionInfo
            Given remote invoke execution info which contains the request information

        Returns
        -------
        RemoteInvokeExecutionInfo
            RemoteInvokeExecutionInfo which contains updated input payload
        """
        for input_mapper in self._request_mappers:
            remote_invoke_input = input_mapper.map(remote_invoke_input)
        return remote_invoke_input

    def _map_output(self, remote_invoke_output: RemoteInvokeResponse) -> RemoteInvokeResponse:
        """
        Maps the given response through the response mapper list.

        Parameters
        ----------
        remote_invoke_output : RemoteInvokeResponse
            Given remote invoke response which contains the payload itself

        Returns
        -------
        RemoteInvokeResponse
            Returns the mapped instance of RemoteInvokeResponse, after applying all configured mappers
        """
        for output_mapper in self._response_mappers:
            remote_invoke_output = output_mapper.map(remote_invoke_output)
        return remote_invoke_output
