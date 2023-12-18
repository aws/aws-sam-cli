from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.lib.local_lambda_service import LocalLambdaService


class TestLocalLambdaService(TestCase):
    def test_initialization(self):
        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        lambda_invoke_context_mock = Mock()

        lambda_invoke_context_mock.local_lambda_runner = lambda_runner_mock
        lambda_invoke_context_mock.stderr = stderr_mock

        service = LocalLambdaService(lambda_invoke_context=lambda_invoke_context_mock, port=3000, host="localhost")

        self.assertEqual(service.port, 3000)
        self.assertEqual(service.host, "localhost")
        self.assertEqual(service.lambda_runner, lambda_runner_mock)
        self.assertEqual(service.stderr_stream, stderr_mock)

    @patch("samcli.commands.local.lib.local_lambda_service.LocalLambdaInvokeService")
    def test_start(self, local_lambda_invoke_service_mock):
        lambda_runner_mock = Mock()
        stderr_mock = Mock()
        lambda_invoke_context_mock = Mock()

        lambda_context_mock = Mock()
        local_lambda_invoke_service_mock.return_value = lambda_context_mock

        lambda_invoke_context_mock.local_lambda_runner = lambda_runner_mock
        lambda_invoke_context_mock.stderr = stderr_mock

        service = LocalLambdaService(lambda_invoke_context=lambda_invoke_context_mock, port=3000, host="localhost")

        service.start()

        local_lambda_invoke_service_mock.assert_called_once_with(
            lambda_runner=lambda_runner_mock, port=3000, host="localhost", stderr=stderr_mock
        )
        lambda_context_mock.create.assert_called_once()
        lambda_context_mock.run.assert_called_once()
