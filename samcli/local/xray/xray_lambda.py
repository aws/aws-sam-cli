"""
Replicate AWS X-Ray Lambda integration locally.
"""
import logging
from aws_xray_sdk.core import xray_recorder

LOG = logging.getLogger(__name__)


class XrayLambdaIntegration(object):
    def __init__(self, xray_daemon_address):
        """
        Creates an XrayLambdaIntegration for a Lambda runtime.
        XrayLambdaIntegration should run in Lambda's own thread since
        xray_recorder's context can only synchronously handle one active segment at a time.
        """
        self._xray_daemon_address = xray_daemon_address
        self._current_trace_id = ""

    def begin_lambda_segment(self, function_name):
        """
        Replicates Lambda X-Ray integration segments.

        :param string function_name: Name of the Lambda function being invoked.
        """
        xray_recorder.configure(sampling=False, daemon_address='127.0.0.1:2000')

        # Replicate AWS::Lambda segment
        xray_recorder.begin_segment(function_name)
        lambda_segment = xray_recorder.current_segment()
        lambda_segment.set_service(None)
        setattr(lambda_segment, 'origin', 'AWS::Lambda')
        xray_recorder.end_segment()

        # Replicate AWS::Lambda::Function and Initialization subsegment
        xray_recorder.begin_segment(function_name, traceid=lambda_segment.trace_id, parent_id=lambda_segment.id)

        lambda_function_segment = xray_recorder.current_segment()
        lambda_function_segment.set_service(None)
        setattr(lambda_function_segment, 'origin', 'AWS::Lambda::Function')

        xray_recorder.begin_subsegment('Initialization')
        xray_recorder.end_subsegment()
        # Don't end AWS::Lambda::Function segment yet. To be ended after the user's function returns.

        # Generate the Trace ID environment variable
        self._current_trace_id = 'Root={trace_id};Parent={parent_id};Sampled=1'.format(
            trace_id=lambda_segment.trace_id, parent_id=lambda_function_segment.id)

    def end_lambda_segment(self):
        """
        Call to end AWS::Lambda::Function segment after invoked user's lambda function returns.
        """
        xray_recorder.end_segment()

    def get_lambda_envs(self):
        """
        Prepare X-Ray related Lambda environment variables.

        :return dict: X-Ray environment variables.
        """
        return {
            '_AWS_XRAY_DAEMON_ADDRESS': self._xray_daemon_address,
            '_AWS_XRAY_DAEMON_PORT': '2000',
            'AWS_XRAY_DAEMON_ADDRESS': self._xray_daemon_address + ':2000',
            'AWS_XRAY_CONTEXT_MISSING': 'LOG_ERROR',
            '_X_AMZN_TRACE_ID': self._current_trace_id
        }
