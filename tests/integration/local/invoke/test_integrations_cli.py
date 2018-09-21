import json

from nose_parameterized import parameterized
from subprocess import Popen, PIPE
from timeit import default_timer as timer

from .invoke_integ_base import InvokeIntegBase


class TestSamPython36HelloWorldIntegration(InvokeIntegBase):

    def test_invoke_returncode_is_zero(self):
        command_list = self.get_command_list("HelloWorldServerlessFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        process = Popen(command_list, stdout=PIPE)
        return_code = process.wait()

        self.assertEquals(return_code, 0)

    def test_invoke_returns_execpted_results(self):
        command_list = self.get_command_list("HelloWorldServerlessFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()
        self.assertEquals(process_stdout.decode('utf-8'), '"Hello world"')

    def test_invoke_of_lambda_function(self):
        command_list = self.get_command_list("HelloWorldLambdaFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()
        self.assertEquals(process_stdout.decode('utf-8'), '"Hello world"')

    @parameterized.expand([
        ("TimeoutFunction"),
        ("TimeoutFunctionWithParameter"),
    ])
    def test_invoke_with_timeout_set(self, function_name):
        command_list = self.get_command_list(function_name,
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        start = timer()
        process = Popen(command_list, stdout=PIPE)
        return_code = process.wait()
        end = timer()

        wall_clock_cli_duration = end - start

        process_stdout = b"".join(process.stdout.readlines()).strip()

        # validate the time of the cli (timeout is set to 5s)
        self.assertGreater(wall_clock_cli_duration, 5)
        self.assertLess(wall_clock_cli_duration, 20)

        self.assertEquals(return_code, 0)
        self.assertEquals(process_stdout.decode('utf-8'), "", msg="The return statement in the LambdaFunction "
                                                                  "should never return leading to an empty string")

    def test_invoke_with_env_vars(self):
        command_list = self.get_command_list("EchoCustomEnvVarFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path,
                                             env_var_path=self.env_var_path)

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()
        self.assertEquals(process_stdout.decode('utf-8'), '"MyVar"')

    def test_invoke_when_function_writes_stdout(self):
        command_list = self.get_command_list("WriteToStdoutFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()).strip()
        process_stderr = b"".join(process.stderr.readlines()).strip()

        self.assertIn("Docker Lambda is writing to stdout", process_stderr.decode('utf-8'))
        self.assertIn("wrote to stdout", process_stdout.decode('utf-8'))

    def test_invoke_when_function_writes_stderr(self):
        command_list = self.get_command_list("WriteToStderrFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        process = Popen(command_list, stderr=PIPE)
        process.wait()

        process_stderr = b"".join(process.stderr.readlines()).strip()

        self.assertIn("Docker Lambda is writing to stderr", process_stderr.decode('utf-8'))

    def test_invoke_returns_expected_result_when_no_event_given(self):
        command_list = self.get_command_list("EchoEventFunction", template_path=self.template_path)
        command_list.append("--no-event")
        process = Popen(command_list, stdout=PIPE)
        return_code = process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()

        self.assertEquals(return_code, 0)
        self.assertEquals("{}", process_stdout.decode('utf-8'))

    def test_invoke_raises_exception_with_noargs_and_event(self):
        command_list = self.get_command_list("HelloWorldLambdaFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path)
        command_list.append("--no-event")
        process = Popen(command_list, stderr=PIPE)
        process.wait()

        process_stderr = b"".join(process.stderr.readlines()).strip()
        error_output = process_stderr.decode('utf-8')
        self.assertIn("no_event and event cannot be used together. Please provide only one.", error_output)

    def test_invoke_with_env_using_parameters(self):
        command_list = self.get_command_list("EchoEnvWithParameters",
                                             template_path=self.template_path,
                                             event_path=self.event_path,
                                             parameter_overrides={
                                                 "MyRuntimeVersion": "v0",
                                                 "DefaultTimeout": "100"
                                             })

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()
        environ = json.loads(process_stdout.decode('utf-8'))

        self.assertEquals(environ["Region"], "us-east-1")
        self.assertEquals(environ["AccountId"], "123456789012")
        self.assertEquals(environ["Partition"], "aws")
        self.assertEquals(environ["StackName"], "local")
        self.assertEquals(environ["StackId"], "arn:aws:cloudformation:us-east-1:123456789012:stack/"
                                              "local/51af3dc0-da77-11e4-872e-1234567db123",)

        self.assertEquals(environ["URLSuffix"], "localhost")
        self.assertEquals(environ["Timeout"], "100")
        self.assertEquals(environ["MyRuntimeVersion"], "v0")

    def test_invoke_with_env_using_parameters_with_custom_region(self):
        custom_region = "my-custom-region"

        command_list = self.get_command_list("EchoEnvWithParameters",
                                             template_path=self.template_path,
                                             event_path=self.event_path,
                                             region=custom_region
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()
        environ = json.loads(process_stdout.decode('utf-8'))

        self.assertEquals(environ["Region"], custom_region)
