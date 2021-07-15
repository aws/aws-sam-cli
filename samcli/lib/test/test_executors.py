"""
Abstract class definitions and generic implementations for test execution
"""
import json
import logging
from abc import abstractmethod, ABC
from io import TextIOWrapper
from pathlib import Path
from typing import List, Optional, Union, Callable, cast, Any

LOG = logging.getLogger(__name__)


class TestExecutionInfo:
    """
    Keeps request and response information about test execution

    payload: payload string given by the customer
    payload_file: if file is given, this points to its location

    response: response object returned from boto3 action
    exception: if an exception is been thrown, it will be stored here
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

    def is_file_provided(self):
        return self.payload_file

    @property
    def payload_file_path(self) -> Optional[TextIOWrapper]:
        return self.payload_file if self.is_file_provided() else None

    def is_succeeded(self):
        return self.response


class TestRequestResponseMapper(ABC):
    """
    Mapper definition which can be used map test requests or responses.

    For instance, if a string provided where JSON is required, a mapper can convert given string
    into JSON object for request.

    Or for a response object, if it contains streaming results, a mapper can convert them back
    to string to display on
    """

    @abstractmethod
    def map(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        raise NotImplementedError()


class ResponseObjectToJsonStringMapper(TestRequestResponseMapper):
    def map(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        LOG.debug("Converting response object into JSON")
        test_input.response = json.dumps(test_input.response, indent=2)
        return test_input


class BotoActionExecutor(ABC):
    """
    Executes a specific boto3 service action and updates the response of the TestExecutionInfo object
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

    def execute(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        """
        Executes boto3 API and updates response or exception object depending on the result

        Parameters
        ----------
        test_input : TestExecutionInfo
            TestExecutionInfo details which contains payload or payload file information

        Returns : TestExecutionInfo
        -------
            Updates response or exception fields of given input and returns it
        """
        action_executor: Callable[[Any], dict]
        payload: Union[str, Path]

        # if a file pointed is provided for payload, use specific payload and its function here
        if test_input.is_file_provided():
            action_executor = self._execute_action_file
            payload = cast(Path, test_input.payload_file_path)
        else:
            action_executor = self._execute_action
            payload = cast(str, test_input.payload)

        # execute boto3 API, and update result if it is successful, update exception otherwise
        try:
            action_response = action_executor(payload)
            test_input.response = action_response
        except Exception as e:
            LOG.error("Failed while executing boto action", exc_info=e)
            test_input.exception = e

        return test_input


class TestExecutor:
    """
    Generic TestExecutor, which contains request mappers, response mappers and boto action executor.

    Input is been updated with the given list of request mappers.
    Then updated input have been passed to boto action executor to actually call the API
    Once the result is returned, if it is successful, response have been mapped with list of response mappers
    """

    _request_mappers: List[TestRequestResponseMapper]
    _response_mappers: List[TestRequestResponseMapper]
    _boto_action_executor: BotoActionExecutor

    def __init__(
        self,
        request_mappers: List[TestRequestResponseMapper],
        response_mappers: List[TestRequestResponseMapper],
        boto_action_executor: BotoActionExecutor,
    ):
        self._request_mappers = request_mappers
        self._response_mappers = response_mappers
        self._boto_action_executor = boto_action_executor

    def execute(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        test_input = self._map_input(test_input)
        test_output = self._boto_action_executor.execute(test_input)

        # call output mappers if the action is succeeded
        if test_output.is_succeeded():
            return self._map_output(test_output)

        return test_output

    def _map_input(self, test_input: TestExecutionInfo) -> TestExecutionInfo:
        """
        Maps the given input through the request mapper list.

        Parameters
        ----------
        test_input : TestExecutionInfo
            Given test execution info which contains the request information

        Returns : TestExecutionInfo
        -------
            TestExecutionInfo which contains updated input payload
        """
        for input_mapper in self._request_mappers:
            test_input = input_mapper.map(test_input)
        return test_input

    def _map_output(self, test_output: TestExecutionInfo) -> TestExecutionInfo:
        """
        Maps the given response through the response mapper list.

        Parameters
        ----------
        test_output : TestExecutionInfo
            Given test execution info which contains the response information

        Returns : TestExecutionInfo
        -------
            TestExecutionInfo which contains updated response
        """
        for output_mapper in self._response_mappers:
            test_output = output_mapper.map(test_output)
        return test_output
