import json
import os
import copy
from unittest import skipIf

from docker.errors import APIError, ImageNotFound
from parameterized import parameterized
from subprocess import Popen, PIPE, TimeoutExpired
from timeit import default_timer as timer
import pytest
import docker

from .invoke_integ_base import InvokeIntegBase
from tests.testing_utils import IS_WINDOWS, RUNNING_ON_CI, CI_OVERRIDE

from pathlib import Path

from samcli import __version__ as version
from samcli.local.docker.lambda_image import RAPID_IMAGE_TAG_PREFIX
from samcli.lib.utils.architecture import X86_64

TIMEOUT = 300


@skipIf(
    ((IS_WINDOWS and RUNNING_ON_CI) and not CI_OVERRIDE),
    "Skip build tests on windows when running in CI unless overridden",
)
class TestSamPython36HelloWorldIntegrationImages(InvokeIntegBase):
    template = Path("template_image.yaml")

    @classmethod
    def setUpClass(cls):
        super(TestSamPython36HelloWorldIntegrationImages, cls).setUpClass()
        cls.client = docker.from_env()
        cls.image_name = "sam-test-lambdaimage"
        cls.docker_tag = f"{cls.image_name}:v1"
        cls.test_data_invoke_path = str(Path(__file__).resolve().parents[2].joinpath("testdata", "invoke"))
        # Directly build an image that will be used across all local invokes in this class.
        for log in cls.client.api.build(
            path=cls.test_data_invoke_path, dockerfile="Dockerfile", tag=cls.docker_tag, decode=True
        ):
            print(log)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.api.remove_image(cls.docker_tag)
            cls.client.api.remove_image(f"{cls.image_name}:{RAPID_IMAGE_TAG_PREFIX}-{X86_64}")
        except APIError:
            pass

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returncode_is_zero(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 0)

    @parameterized.expand(
        [
            ("MyReallyCoolFunction",),
            ("HelloWorldServerlessFunction",),
            ("HelloWorldServerlessWithFunctionNameRefFunction",),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_execpted_results(self, function_name):
        command_list = self.get_command_list(
            function_name, template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_of_lambda_function(self):
        command_list = self.get_command_list(
            "HelloWorldLambdaFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_of_lambda_function_with_function_name_override(self):
        command_list = self.get_command_list(
            "func-name-override", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @parameterized.expand(
        [("TimeoutFunction"), ("TimeoutFunctionWithParameter"), ("TimeoutFunctionWithStringParameter")]
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_timeout_set(self, function_name):
        command_list = self.get_command_list(
            function_name, template_path=self.template_path, event_path=self.event_path
        )

        start = timer()
        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        end = timer()

        wall_clock_cli_duration = end - start

        process_stdout = stdout.strip()

        # validate the time of the cli (timeout is set to 5s)
        self.assertGreater(wall_clock_cli_duration, 5)
        self.assertLess(wall_clock_cli_duration, 20)

        self.assertEqual(process.returncode, 0)
        self.assertEqual(
            process_stdout.decode("utf-8"),
            "",
            msg="The return statement in the LambdaFunction " "should never return leading to an empty string",
        )

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_vars(self):
        command_list = self.get_command_list(
            "EchoCustomEnvVarFunction",
            template_path=self.template_path,
            event_path=self.event_path,
            env_var_path=self.env_var_path,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"MyVar"')

    @parameterized.expand([("EchoCustomEnvVarWithFunctionNameDefinedFunction"), ("customname")])
    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_vars_with_functionname_defined(self, function_name):
        command_list = self.get_command_list(
            function_name, template_path=self.template_path, event_path=self.event_path, env_var_path=self.env_var_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"MyVar"')

    @parameterized.expand([("EchoGlobalCustomEnvVarFunction")])
    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_global_env_vars_function(self, function_name):
        command_list = self.get_command_list(
            function_name, template_path=self.template_path, event_path=self.event_path, env_var_path=self.env_var_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"GlobalVar"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stdout(self):
        command_list = self.get_command_list(
            "WriteToStdoutFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        process_stderr = stderr.strip()

        self.assertIn("Docker Lambda is writing to stdout", process_stderr.decode("utf-8"))
        self.assertIn("wrote to stdout", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_when_function_writes_stderr(self):
        command_list = self.get_command_list(
            "WriteToStderrFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()

        self.assertIn("Docker Lambda is writing to stderr", process_stderr.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_result_when_no_event_given(self):
        command_list = self.get_command_list("EchoEventFunction", template_path=self.template_path)
        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process.returncode, 0)
        self.assertEqual("{}", process_stdout.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_using_parameters(self):
        command_list = self.get_command_list(
            "EchoEnvWithParameters",
            template_path=self.template_path,
            event_path=self.event_path,
            parameter_overrides={"DefaultTimeout": "100"},
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertEqual(environ["Region"], "us-east-1")
        self.assertEqual(environ["AccountId"], "123456789012")
        self.assertEqual(environ["Partition"], "aws")
        self.assertEqual(environ["StackName"], "local")
        self.assertEqual(
            environ["StackId"],
            "arn:aws:cloudformation:us-east-1:123456789012:stack/" "local/51af3dc0-da77-11e4-872e-1234567db123",
        )

        self.assertEqual(environ["URLSuffix"], "localhost")
        self.assertEqual(environ["Timeout"], "100")
        self.assertEqual(environ["EmptyDefaultParameter"], "")

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_using_parameters_with_custom_region(self):
        custom_region = "my-custom-region"

        command_list = self.get_command_list(
            "EchoEnvWithParameters", template_path=self.template_path, event_path=self.event_path, region=custom_region
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertEqual(environ["Region"], custom_region)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_env_with_aws_creds(self):
        custom_region = "my-custom-region"
        key = "key"
        secret = "secret"
        session = "session"

        command_list = self.get_command_list(
            "EchoEnvWithParameters", template_path=self.template_path, event_path=self.event_path
        )

        env = copy.deepcopy(dict(os.environ))
        env["AWS_DEFAULT_REGION"] = custom_region
        env["AWS_REGION"] = custom_region
        env["AWS_ACCESS_KEY_ID"] = key
        env["AWS_SECRET_ACCESS_KEY"] = secret
        env["AWS_SESSION_TOKEN"] = session

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertEqual(environ["AWS_DEFAULT_REGION"], custom_region)
        self.assertEqual(environ["AWS_REGION"], custom_region)
        self.assertEqual(environ["AWS_ACCESS_KEY_ID"], key)
        self.assertEqual(environ["AWS_SECRET_ACCESS_KEY"], secret)
        self.assertEqual(environ["AWS_SESSION_TOKEN"], session)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_docker_network_of_host(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction",
            template_path=self.template_path,
            event_path=self.event_path,
            docker_network="host",
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    @skipIf(IS_WINDOWS, "The test hangs on Windows due to trying to attach to a non-existing network")
    def test_invoke_with_docker_network_of_host_in_env_var(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        env = os.environ.copy()
        env["SAM_DOCKER_NETWORK"] = "non-existing-network"

        process = Popen(command_list, stderr=PIPE, env=env)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()

        self.assertIn('Not Found ("network non-existing-network not found")', process_stderr.decode("utf-8"))

    @pytest.mark.flaky(reruns=3)
    def test_sam_template_file_env_var_set(self):
        command_list = self.get_command_list("HelloWorldFunctionInNonDefaultTemplate", event_path=self.event_path)

        self.test_data_path.joinpath("invoke", "sam-template-image.yaml")
        env = os.environ.copy()
        env["SAM_TEMPLATE_FILE"] = str(self.test_data_path.joinpath("invoke", "sam-template-image.yaml"))

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    def test_invoke_with_error_during_image_build(self):
        command_list = self.get_command_list(
            "ImageDoesntExistFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Error building docker image: pull access denied for non-existing-image",
        )
        self.assertEqual(process.returncode, 1)


class TestDeleteOldRapidImages(InvokeIntegBase):
    template = Path("template_image.yaml")

    @classmethod
    def setUpClass(cls):
        super(TestDeleteOldRapidImages, cls).setUpClass()
        cls.client = docker.from_env()
        cls.repo = "sam-test-lambdaimage"
        cls.tag = f"{cls.repo}:v1"
        cls.test_data_invoke_path = str(Path(__file__).resolve().parents[2].joinpath("testdata", "invoke"))
        # Directly build an image that will be used across all local invokes in this class.
        for log in cls.client.api.build(
            path=cls.test_data_invoke_path, dockerfile="Dockerfile", tag=cls.tag, decode=True, nocache=True
        ):
            print(log)
        cls.other_repo = "test-delete-old-rapid-images-other-repo"
        cls.other_repo_tags = [f"{cls.other_repo}:v1", f"{cls.other_repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.client.api.remove_image(cls.tag)
        except APIError:
            pass

    def setUp(self):
        self.old_rapid_image_tags = [
            f"{self.repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.01",
            f"{self.repo}:{RAPID_IMAGE_TAG_PREFIX}-0.00.02",
        ]
        for tag in self.old_rapid_image_tags:
            for log in self.client.api.build(
                path=self.test_data_invoke_path, dockerfile="Dockerfile", tag=tag, decode=True, nocache=True
            ):
                print(log)
        self.new_rapid_image_tag = f"{self.repo}:{RAPID_IMAGE_TAG_PREFIX}-{X86_64}"

    def tearDown(self):
        for tag in self.old_rapid_image_tags + [self.new_rapid_image_tag] + self.other_repo_tags:
            try:
                self.client.api.remove_image(tag)
            except APIError:
                pass

    @pytest.mark.flaky(reruns=3)
    def test_building_new_rapid_image_removes_old_rapid_images(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        for tag in self.old_rapid_image_tags:
            self.assertRaises(ImageNotFound, self.client.images.get, tag)
        self.client.images.get(self.new_rapid_image_tag)
        self.client.images.get(f"{self.repo}:v1")

    @pytest.mark.flaky(reruns=3)
    def test_building_existing_rapid_image_does_not_remove_old_rapid_images(self):
        for log in self.client.api.build(
            path=self.test_data_invoke_path,
            dockerfile="Dockerfile",
            tag=self.new_rapid_image_tag,
            decode=True,
            nocache=True,
        ):
            print(log)

        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        for tag in self.old_rapid_image_tags:
            self.client.images.get(tag)
        self.client.images.get(self.new_rapid_image_tag)
        self.client.images.get(f"{self.repo}:v1")

    @pytest.mark.flaky(reruns=3)
    def test_building_new_rapid_image_doesnt_remove_images_in_other_repos(self):
        for tag in self.other_repo_tags:
            for log in self.client.api.build(
                path=self.test_data_invoke_path, dockerfile="Dockerfile", tag=tag, decode=True, nocache=True
            ):
                print(log)

        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        for tag in self.other_repo_tags:
            self.client.images.get(tag)
