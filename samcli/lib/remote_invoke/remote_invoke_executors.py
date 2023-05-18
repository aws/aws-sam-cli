"""
Abstract class definitions and generic implementations for remote invoke
"""
import json
import logging
from abc import ABC, abstractmethod
from io import TextIOWrapper
from pathlib import Path
from typing import Any, Callable, List, Optional, Union, cast

LOG = logging.getLogger(__name__)


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

    # Response related properties
    response: Optional[Union[dict, str]]
    exception: Optional[Exception]

    def __init__(self, payload: Optional[Union[str, List, dict]], payload_file: Optional[TextIOWrapper]):
        self.payload = payload
        self.payload_file = payload_file
        self.response = None
        self.exception = None

    def is_file_provided(self) -> bool:
        return bool(self.payload_file)

    @property
    def payload_file_path(self) -> Optional[TextIOWrapper]:
        return self.payload_file if self.is_file_provided() else None

    def is_succeeded(self) -> bool:
        return bool(self.response)


class RemoteInvokeRequestResponseMapper(ABC):
    """
    Mapper definition which can be used map remote invoke requests or responses.

    For instance, if a string provided where JSON is required, a mapper can convert given string
    into JSON object for request.

    Or for a response object, if it contains streaming results, a mapper can convert them back
    to string to display on
    """

    @abstractmethod
    def map(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        raise NotImplementedError()


class ResponseObjectToJsonStringMapper(RemoteInvokeRequestResponseMapper):
    """
    Maps response object inside RemoteInvokeExecutionInfo into formatted JSON string with multiple lines
    """

    def map(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        LOG.debug("Converting response object into JSON")
        remote_invoke_input.response = json.dumps(remote_invoke_input.response, indent=2)
        return remote_invoke_input


class BotoActionExecutor(ABC):
    """
    Executes a specific boto3 service action and updates the response of the RemoteInvokeExecutionInfo object
    If execution throws an exception, it updates the exception information as well
    """

    @abstractmethod
    def _execute_action(self, payload: str) -> dict:
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

    def _execute_action_file(self, payload_file: TextIOWrapper) -> dict:
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

    def execute(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        """
        Executes boto3 API and updates response or exception object depending on the result

        Parameters
        ----------
        remote_invoke_input : RemoteInvokeExecutionInfo
            RemoteInvokeExecutionInfo details which contains payload or payload file information

        Returns : RemoteInvokeExecutionInfo
        -------
            Updates response or exception fields of given input and returns it
        """
        action_executor: Callable[[Any], dict]
        payload: Union[str, Path]

        # if a file pointed is provided for payload, use specific payload and its function here
        if remote_invoke_input.is_file_provided():
            action_executor = self._execute_action_file
            payload = cast(Path, remote_invoke_input.payload_file_path)
        else:
            action_executor = self._execute_action
            payload = cast(str, remote_invoke_input.payload)

        # execute boto3 API, and update result if it is successful, update exception otherwise
        try:
            action_response = action_executor(payload)
            remote_invoke_input.response = action_response
        except Exception as e:
            LOG.error("Failed while executing boto action", exc_info=e)
            remote_invoke_input.exception = e

        return remote_invoke_input


class RemoteInvokeExecutor:
    """
    Generic RemoteInvokeExecutor, which contains request mappers, response mappers and boto action executor.

    Input is been updated with the given list of request mappers.
    Then updated input have been passed to boto action executor to actually call the API
    Once the result is returned, if it is successful, response have been mapped with list of response mappers
    """

    _request_mappers: List[RemoteInvokeRequestResponseMapper]
    _response_mappers: List[RemoteInvokeRequestResponseMapper]
    _boto_action_executor: BotoActionExecutor

    def __init__(
        self,
        request_mappers: List[RemoteInvokeRequestResponseMapper],
        response_mappers: List[RemoteInvokeRequestResponseMapper],
        boto_action_executor: BotoActionExecutor,
    ):
        self._request_mappers = request_mappers
        self._response_mappers = response_mappers
        self._boto_action_executor = boto_action_executor

    def execute(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        """
        First runs all mappers for request object to get the final version of it.
        Then invokes the BotoActionExecutor to get the result
        And finally, runs all mappers for the response object to get the final form of it.
        """
        remote_invoke_input = self._map_input(remote_invoke_input)
        remote_invoke_output = self._boto_action_executor.execute(remote_invoke_input)

        # call output mappers if the action is succeeded
        if remote_invoke_output.is_succeeded():
            return self._map_output(remote_invoke_output)

        return remote_invoke_output

    def _map_input(self, remote_invoke_input: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        """
        Maps the given input through the request mapper list.

        Parameters
        ----------
        remote_invoke_input : RemoteInvokeExecutionInfo
            Given remote invoke execution info which contains the request information

        Returns : RemoteInvokeExecutionInfo
        -------
            RemoteInvokeExecutionInfo which contains updated input payload
        """
        for input_mapper in self._request_mappers:
            remote_invoke_input = input_mapper.map(remote_invoke_input)
        return remote_invoke_input

    def _map_output(self, remote_invoke_output: RemoteInvokeExecutionInfo) -> RemoteInvokeExecutionInfo:
        """
        Maps the given response through the response mapper list.

        Parameters
        ----------
        remote_invoke_output : RemoteInvokeExecutionInfo
            Given remote invoke execution info which contains the response information

        Returns : RemoteInvokeExecutionInfo
        -------
            RemoteInvokeExecutionInfo which contains updated response
        """
        for output_mapper in self._response_mappers:
            remote_invoke_output = output_mapper.map(remote_invoke_output)
        return remote_invoke_output
