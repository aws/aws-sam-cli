"""
Invokes remote Lambda
"""
import json
import logging
from json.decoder import JSONDecodeError

LOG = logging.getLogger(__name__)


class InvokeRunner:
    """
    Invokes a remote lambda with a given event payload
    """

    def __init__(self, lambda_client=None):
        """
        Initialize the runner

        Parameters
        ----------
        lambda_client
            Lambda Client from AWS SDK
        """
        self.lambda_client = lambda_client

    def invoke(self, lambda_id, event, qualifier=None, stdout=None, stderr=None):
        """
        Invokes a lambda under a given event and writes its output to the terminal or a given file.

        Parameters
        ----------
        lambda_id : string
            Lambda Physical ID.

        event : dict
            Event payload

        qualifier : string
            Optional Function version to execute

        stdout : StreamWriter
            Optional Stream writer to write the output of the Lambda function to.

        stderr : StreamWriter
            Optional Stream writer to write the Lambda runtime logs to.
        """

        kwargs = {
            "FunctionName": lambda_id,
            "InvocationType": "RequestResponse",
            # "LogType": "Tail",
            "Payload": event,
        }

        if qualifier:
            kwargs.update({
                "Qualifier": qualifier
            })

        result = self.lambda_client.invoke(**kwargs)

        payload = result['Payload'].read()
        try:
            formatted_payload = json.dumps(json.loads(payload), indent=4, sort_keys=True)
            stdout.write(bytes(formatted_payload, encoding="utf-8") + b"\n")

        except JSONDecodeError as ex:
            # The response probably isn't in json format, print the raw payload instead
            stdout.write(payload + b"\n")
