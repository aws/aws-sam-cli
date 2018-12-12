import shutil
import io
import logging
import json
import random
import threading

from collections import namedtuple
from timeit import default_timer as timer
from unittest import TestCase
from parameterized import parameterized, param

from tests.functional.function_code import nodejs_lambda, make_zip, ECHO_CODE, SLEEP_CODE, GET_ENV_VAR
from samcli.local.docker.manager import ContainerManager
from samcli.local.lambdafn.runtime import LambdaRuntime
from samcli.local.lambdafn.config import FunctionConfig
from samcli.local.layers.layer_downloader import LayerDownloader
from samcli.local.docker.lambda_image import LambdaImage

logging.basicConfig(level=logging.INFO)

RUNTIME = "nodejs4.3"
HANDLER = "index.handler"
MEMORY = 1024


class TestLambdaRuntime(TestCase):

    # Approx Number of seconds it takes to startup a Docker container. This helps us measure
    # the approx time that the Lambda Function actually ran for
    CONTAINER_STARTUP_OVERHEAD_SECONDS = 5

    def setUp(self):
        self.code_dir = {
            "echo": nodejs_lambda(ECHO_CODE),
            "sleep": nodejs_lambda(SLEEP_CODE),
            "envvar": nodejs_lambda(GET_ENV_VAR)
        }

        self.container_manager = ContainerManager()
        layer_downloader = LayerDownloader("./", "./")
        self.lambda_image = LambdaImage(layer_downloader, False, False)
        self.runtime = LambdaRuntime(self.container_manager, self.lambda_image)

    def tearDown(self):
        for _, dir in self.code_dir.items():
            shutil.rmtree(dir)

    def test_echo_function(self):
        timeout = 3
        input_event = '{"a":"b"}'
        expected_output = b'{"a":"b"}'

        config = FunctionConfig(name="helloworld",
                                runtime=RUNTIME,
                                handler=HANDLER,
                                code_abs_path=self.code_dir["echo"],
                                layers=[],
                                timeout=timeout)

        stdout_stream = io.BytesIO()
        self.runtime.invoke(config, input_event, stdout=stdout_stream)

        actual_output = stdout_stream.getvalue()
        self.assertEquals(actual_output.strip(), expected_output)

    def test_function_timeout(self):
        """
        Setup a short timeout and verify that the container is stopped
        """
        stdout_stream = io.BytesIO()
        timeout = 1  # 1 second timeout
        sleep_seconds = 20  # Ask the function to sleep for 20 seconds

        config = FunctionConfig(name="sleep_timeout",
                                runtime=RUNTIME,
                                handler=HANDLER,
                                code_abs_path=self.code_dir["sleep"],
                                layers=[],
                                timeout=timeout)

        # Measure the actual duration of execution
        start = timer()
        self.runtime.invoke(config, str(sleep_seconds), stdout=stdout_stream)
        end = timer()

        # Make sure that the wall clock duration is around the ballpark of timeout value
        wall_clock_func_duration = end - start
        print("Function completed in {} seconds".format(wall_clock_func_duration))
        # The function should *not* preemptively stop
        self.assertGreater(wall_clock_func_duration, timeout - 1)
        # The function should not run for much longer than timeout.
        self.assertLess(wall_clock_func_duration, timeout + self.CONTAINER_STARTUP_OVERHEAD_SECONDS)

        # There should be no output from the function because timer was interrupted
        actual_output = stdout_stream.getvalue()
        self.assertEquals(actual_output.strip(), b"")

    @parameterized.expand([
        ("zip"),
        ("jar"),
        ("ZIP"),
        ("JAR")
    ])
    def test_echo_function_with_zip_file(self, file_name_extension):
        timeout = 3
        input_event = '"this input should be echoed"'
        expected_output = b'"this input should be echoed"'

        code_dir = self.code_dir["echo"]
        with make_zip(code_dir, file_name_extension) as code_zip_path:

            config = FunctionConfig(name="helloworld",
                                    runtime=RUNTIME,
                                    handler=HANDLER,
                                    code_abs_path=code_zip_path,
                                    layers=[],
                                    timeout=timeout)

            stdout_stream = io.BytesIO()
            self.runtime.invoke(config, input_event, stdout=stdout_stream)

            actual_output = stdout_stream.getvalue()
            self.assertEquals(actual_output.strip(), expected_output)

    def test_check_environment_variables(self):
        variables = {"var1": "value1", "var2": "value2"}
        aws_creds = {"region": "ap-south-1", "key": "mykey", "secret": "mysecret"}

        timeout = 30
        input_event = ""
        stdout_stream = io.BytesIO()
        expected_output = {
            "AWS_SAM_LOCAL": "true",
            "AWS_LAMBDA_FUNCTION_MEMORY_SIZE": "1024",
            "AWS_LAMBDA_FUNCTION_TIMEOUT": "30",
            "AWS_LAMBDA_FUNCTION_HANDLER": "index.handler",

            # Values coming from AWS Credentials
            "AWS_REGION": "ap-south-1",
            "AWS_DEFAULT_REGION": "ap-south-1",
            "AWS_ACCESS_KEY_ID": "mykey",
            "AWS_SECRET_ACCESS_KEY": "mysecret",

            # Custom environment variables
            "var1": "value1",
            "var2": "value2"
        }

        config = FunctionConfig(name="helloworld",
                                runtime=RUNTIME,
                                handler=HANDLER,
                                code_abs_path=self.code_dir["envvar"],
                                layers=[],
                                memory=MEMORY,
                                timeout=timeout)

        # Set the appropriate environment variables
        config.env_vars.variables = variables
        config.env_vars.aws_creds = aws_creds

        self.runtime.invoke(config, input_event, stdout=stdout_stream)

        actual_output = json.loads(stdout_stream.getvalue().strip().decode('utf-8'))  # Output is a JSON String. Deserialize.

        # Make sure all key/value from expected_output is present in actual_output
        for key, value in expected_output.items():
            # Do the key check first to print a nice error error message when it fails
            self.assertTrue(key in actual_output, "'{}' should be in environment variable output".format(key))
            self.assertEquals(actual_output[key], expected_output[key],
                              "Value of environment variable '{}' differs fromm expectation".format(key))


class TestLambdaRuntime_MultipleInvokes(TestCase):

    def setUp(self):
        self.code_dir = nodejs_lambda(SLEEP_CODE)

        Input = namedtuple('Input', ["timeout", "sleep", "check_stdout"])
        self.inputs = [
            Input(sleep=1, timeout=10, check_stdout=True),
            Input(sleep=2, timeout=10, check_stdout=True),
            Input(sleep=3, timeout=10, check_stdout=True),
            Input(sleep=5, timeout=10, check_stdout=True),
            Input(sleep=8, timeout=10, check_stdout=True),
            Input(sleep=13, timeout=12, check_stdout=False),  # Must timeout
            Input(sleep=21, timeout=20, check_stdout=False),  # Must timeout. So stdout will be empty
        ]
        random.shuffle(self.inputs)

        container_manager = ContainerManager()
        layer_downloader = LayerDownloader("./", "./")
        self.lambda_image = LambdaImage(layer_downloader, False, False)
        self.runtime = LambdaRuntime(container_manager, self.lambda_image)

    def tearDown(self):
        shutil.rmtree(self.code_dir)

    def _invoke_sleep(self, timeout, sleep_duration, check_stdout, exceptions=None):

        name = "sleepfunction_timeout_{}_sleep_{}".format(timeout, sleep_duration)
        print("Invoking function " + name)
        try:
            stdout_stream = io.BytesIO()
            config = FunctionConfig(name=name,
                                    runtime=RUNTIME,
                                    handler=HANDLER,
                                    code_abs_path=self.code_dir,
                                    layers=[],
                                    memory=1024,
                                    timeout=timeout)

            self.runtime.invoke(config, sleep_duration, stdout=stdout_stream)
            actual_output = stdout_stream.getvalue().strip()  # Must output the sleep duration
            if check_stdout:
                self.assertEquals(actual_output.decode('utf-8'), str(sleep_duration))
        except Exception as ex:
            if exceptions is not None:
                exceptions.append({"name": name, "error": ex})
            else:
                raise

    def test_serial(self):
        """
        Making sure we can invoke multiple times on the same ``LambdaRuntime`` object. This is test is necessary to
        catch timer that was not cancelled, race conditions, memory leak issues, etc.
        """

        for input in self.inputs:
            self._invoke_sleep(input.timeout, input.sleep, input.check_stdout)

    def test_parallel(self):
        """
        Making sure we can invoke multiple times on the same ``LambdaRuntime`` object. This is test is necessary to
        catch timer that was not cancelled, race conditions, memory leak issues, etc.
        """

        threads = []

        # Collect all exceptions from threads. This is important because exceptions reported in thread don't bubble
        # to the main thread. Therefore test runner will never catch and fail the test.
        exceptions = []

        for input in self.inputs:

            t = threading.Thread(name='thread', target=self._invoke_sleep,
                                 args=(input.timeout, input.sleep, input.check_stdout, exceptions))
            t.setDaemon(True)
            t.start()
            threads.append(t)

        # Wait for all threads to exit
        for t in threads:
            t.join()

        for e in exceptions:
            print("-------------")
            print("ERROR in function " + e["name"])
            print(e["error"])
            print("-------------")

        if len(exceptions) > 0:
            raise AssertionError("Test failed. See print outputs above for details on the thread that failed")
