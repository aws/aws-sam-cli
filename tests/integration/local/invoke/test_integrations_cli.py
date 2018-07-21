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

    def test_invoke_with_timeout_set(self):
        command_list = self.get_command_list("TimeoutFunction",
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
