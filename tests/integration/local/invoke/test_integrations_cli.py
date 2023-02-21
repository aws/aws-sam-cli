import json
import shutil
import os
import copy
import tempfile
from unittest import skipIf

from parameterized import parameterized, parameterized_class
from subprocess import Popen, PIPE, TimeoutExpired
from timeit import default_timer as timer
import pytest
import docker

from tests.integration.local.invoke.layer_utils import LayerUtils
from .invoke_integ_base import InvokeIntegBase
from tests.testing_utils import IS_WINDOWS, RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY, run_command

# Layers tests require credentials and Appveyor will only add credentials to the env if the PR is from the same repo.
# This is to restrict layers tests to run outside of Appveyor, when the branch is not master and tests are not run by Canary.
SKIP_LAYERS_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY

from pathlib import Path

TIMEOUT = 300


@parameterized_class(
    ("template",),
    [
        (Path("template.yml"),),
        (Path("nested-templates/template-parent.yaml"),),
    ],
)
class TestSamPython37HelloWorldIntegration(InvokeIntegBase):
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

    # https://github.com/aws/aws-sam-cli/issues/2494
    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_utf8_event(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_utf8_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    def test_function_with_metadata(self):
        command_list = self.get_command_list("FunctionWithMetadata", template_path=self.template_path, no_event=True)

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process_stdout.decode("utf-8"), '"Hello World in a different dir"')

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
    def test_invoke_with_invoke_image_provided(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction",
            template_path=self.template_path,
            event_path=self.event_path,
            invoke_image="amazon/aws-sam-cli-emulation-image-python3.7",
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

        process = Popen(command_list, stderr=PIPE, stdout=PIPE)
        try:
            stdout, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()
        process_stdout = stdout.strip()

        self.assertIn("Docker Lambda is writing to stderr", process_stderr.decode("utf-8"))
        self.assertIn("wrote to stderr", process_stdout.decode("utf-8"))

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
            parameter_overrides={"MyRuntimeVersion": "v0", "DefaultTimeout": "100"},
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
        self.assertEqual(environ["MyRuntimeVersion"], "v0")
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

        self.test_data_path.joinpath("invoke", "sam-template.yaml")
        env = os.environ.copy()
        env["SAM_TEMPLATE_FILE"] = str(self.test_data_path.joinpath("invoke", "sam-template.yaml"))

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=TIMEOUT, method="thread")
    def test_skip_pull_image_in_env_var(self):
        docker.from_env().api.pull("lambci/lambda:python3.7")

        command_list = self.get_command_list(
            "HelloWorldLambdaFunction", template_path=self.template_path, event_path=self.event_path
        )

        env = os.environ.copy()
        env["SAM_SKIP_PULL_IMAGE"] = "True"

        process = Popen(command_list, stderr=PIPE, env=env)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()
        self.assertIn("Requested to skip pulling images", process_stderr.decode("utf-8"))

    # For Windows, this test must run with administrator privilege
    @skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_results_from_git_function(self):
        command_list = self.get_command_list(
            "GitLayerFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"git init passed"')

    # For Windows, this test must run with administrator privilege
    @skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
    @pytest.mark.flaky(reruns=3)
    def test_invoke_returns_expected_results_from_git_function_with_parameters(self):
        command_list = self.get_command_list(
            "GitLayerFunctionParameters",
            template_path=self.template_path,
            event_path=self.event_path,
            parameter_overrides={"LayerVersion": "5"},
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        self.assertEqual(process_stdout.decode("utf-8"), '"git init passed"')


class TestSamInstrinsicsAndPlugins(InvokeIntegBase):
    template = Path("template-pseudo-params.yaml")

    @pytest.mark.flaky(reruns=3)
    def test_resolve_instrincs_which_runs_plugins(self):
        command_list = self.get_command_list(
            "HelloWorldServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        # Returned result is dependent on region, but should not be None.
        self.assertIsNotNone(process_stdout.decode("utf-8"), "Invalid ApplicationId")


class TestUsingConfigFiles(InvokeIntegBase):
    template = Path("template.yml")

    def setUp(self):
        self.config_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.config_dir, ignore_errors=True)

    @pytest.mark.flaky(reruns=3)
    def test_existing_env_variables_precedence_over_profiles(self):
        profile = "default"
        custom_config = self._create_config_file(profile)
        custom_cred = self._create_cred_file(profile)

        command_list = self.get_command_list(
            "EchoEnvWithParameters", template_path=self.template_path, event_path=self.event_path
        )

        env = os.environ.copy()

        # Explicitly set environment variables beforehand
        env["AWS_DEFAULT_REGION"] = "sa-east-1"
        env["AWS_REGION"] = "sa-east-1"
        env["AWS_ACCESS_KEY_ID"] = "priority_access_key_id"
        env["AWS_SECRET_ACCESS_KEY"] = "priority_secret_key_id"
        env["AWS_SESSION_TOKEN"] = "priority_secret_token"

        # Setup a custom profile
        env["AWS_CONFIG_FILE"] = custom_config
        env["AWS_SHARED_CREDENTIALS_FILE"] = custom_cred

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        # Environment variables we explicitly set take priority over profiles.
        self.assertEqual(environ["AWS_DEFAULT_REGION"], "sa-east-1")
        self.assertEqual(environ["AWS_REGION"], "sa-east-1")
        self.assertEqual(environ["AWS_ACCESS_KEY_ID"], "priority_access_key_id")
        self.assertEqual(environ["AWS_SECRET_ACCESS_KEY"], "priority_secret_key_id")
        self.assertEqual(environ["AWS_SESSION_TOKEN"], "priority_secret_token")

    @pytest.mark.flaky(reruns=3)
    def test_default_profile_with_custom_configs(self):
        profile = "default"
        custom_config = self._create_config_file(profile)
        custom_cred = self._create_cred_file(profile)

        command_list = self.get_command_list(
            "EchoEnvWithParameters", template_path=self.template_path, event_path=self.event_path
        )

        env = os.environ.copy()

        # Explicitly clean environment variables beforehand
        env.pop("AWS_DEFAULT_REGION", None)
        env.pop("AWS_REGION", None)
        env.pop("AWS_ACCESS_KEY_ID", None)
        env.pop("AWS_SECRET_ACCESS_KEY", None)
        env.pop("AWS_SESSION_TOKEN", None)
        env["AWS_CONFIG_FILE"] = custom_config
        env["AWS_SHARED_CREDENTIALS_FILE"] = custom_cred

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertEqual(environ["AWS_DEFAULT_REGION"], "us-west-1")
        self.assertEqual(environ["AWS_REGION"], "us-west-1")
        self.assertEqual(environ["AWS_ACCESS_KEY_ID"], "someaccesskeyid")
        self.assertEqual(environ["AWS_SECRET_ACCESS_KEY"], "shhhhhthisisasecret")
        self.assertEqual(environ["AWS_SESSION_TOKEN"], "sessiontoken")

    @pytest.mark.flaky(reruns=3)
    def test_custom_profile_with_custom_configs(self):
        custom_config = self._create_config_file("custom")
        custom_cred = self._create_cred_file("custom")

        command_list = self.get_command_list(
            "EchoEnvWithParameters", template_path=self.template_path, event_path=self.event_path, profile="custom"
        )

        env = os.environ.copy()

        # Explicitly clean environment variables beforehand
        env.pop("AWS_DEFAULT_REGION", None)
        env.pop("AWS_REGION", None)
        env.pop("AWS_ACCESS_KEY_ID", None)
        env.pop("AWS_SECRET_ACCESS_KEY", None)
        env.pop("AWS_SESSION_TOKEN", None)
        env["AWS_CONFIG_FILE"] = custom_config
        env["AWS_SHARED_CREDENTIALS_FILE"] = custom_cred

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertEqual(environ["AWS_DEFAULT_REGION"], "us-west-1")
        self.assertEqual(environ["AWS_REGION"], "us-west-1")
        self.assertEqual(environ["AWS_ACCESS_KEY_ID"], "someaccesskeyid")
        self.assertEqual(environ["AWS_SECRET_ACCESS_KEY"], "shhhhhthisisasecret")
        self.assertEqual(environ["AWS_SESSION_TOKEN"], "sessiontoken")

    @pytest.mark.flaky(reruns=3)
    def test_custom_profile_through_envrionment_variables(self):
        # When using a custom profile in a custom location, you need both the config
        # and credential file otherwise we fail to find a region or the profile (depending
        # on which one is provided
        custom_config = self._create_config_file("custom")

        custom_cred = self._create_cred_file("custom")

        command_list = self.get_command_list(
            "EchoEnvWithParameters", template_path=self.template_path, event_path=self.event_path
        )

        env = os.environ.copy()

        # Explicitly clean environment variables beforehand
        env.pop("AWS_DEFAULT_REGION", None)
        env.pop("AWS_REGION", None)
        env.pop("AWS_ACCESS_KEY_ID", None)
        env.pop("AWS_SECRET_ACCESS_KEY", None)
        env.pop("AWS_SESSION_TOKEN", None)
        env["AWS_CONFIG_FILE"] = custom_config
        env["AWS_SHARED_CREDENTIALS_FILE"] = custom_cred
        env["AWS_PROFILE"] = "custom"

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()
        environ = json.loads(process_stdout.decode("utf-8"))

        self.assertEqual(environ["AWS_DEFAULT_REGION"], "us-west-1")
        self.assertEqual(environ["AWS_REGION"], "us-west-1")
        self.assertEqual(environ["AWS_ACCESS_KEY_ID"], "someaccesskeyid")
        self.assertEqual(environ["AWS_SECRET_ACCESS_KEY"], "shhhhhthisisasecret")
        self.assertEqual(environ["AWS_SESSION_TOKEN"], "sessiontoken")

    def _create_config_file(self, profile):
        if profile == "default":
            config_file_content = "[{}]\noutput = json\nregion = us-west-1".format(profile)
        else:
            config_file_content = "[profile {}]\noutput = json\nregion = us-west-1".format(profile)

        custom_config = os.path.join(self.config_dir, "customconfig")
        with open(custom_config, "w") as file:
            file.write(config_file_content)
        return custom_config

    def _create_cred_file(self, profile):
        cred_file_content = "[{}]\naws_access_key_id = someaccesskeyid\naws_secret_access_key = shhhhhthisisasecret \
        \naws_session_token = sessiontoken".format(
            profile
        )
        custom_cred = os.path.join(self.config_dir, "customcred")
        with open(custom_cred, "w") as file:
            file.write(cred_file_content)
        return custom_cred


class TestLayerVersionBase(InvokeIntegBase):
    region = "us-west-2"
    layer_utils = LayerUtils(region=region)

    def setUp(self):
        self.layer_cache = Path().home().joinpath("integ_layer_cache")

    def tearDown(self):
        docker_client = docker.from_env()
        samcli_images = docker_client.images.list(name="samcli/lambda")
        for image in samcli_images:
            docker_client.images.remove(image.id)

        shutil.rmtree(str(self.layer_cache))

    @classmethod
    def setUpClass(cls):
        cls.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerOneArn", "layer1.zip")
        cls.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerTwoArn", "layer2.zip")
        super(TestLayerVersionBase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.layer_utils.delete_layers()
        # Added to handle the case where ^C failed the test due to invalid cleanup of layers
        docker_client = docker.from_env()
        samcli_images = docker_client.images.list(name="samcli/lambda")
        for image in samcli_images:
            docker_client.images.remove(image.id)
        integ_layer_cache_dir = Path().home().joinpath("integ_layer_cache")
        if integ_layer_cache_dir.exists():
            shutil.rmtree(str(integ_layer_cache_dir))

        super(TestLayerVersionBase, cls).tearDownClass()


@parameterized_class(
    ("template",),
    [
        (Path("layers", "layer-template.yml"),),
        (Path("nested-templates", "layer-template-parent.yaml"),),
        (Path("layers", "some-dir", "layer-template-parent.yaml"),),
    ],
)
@skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
class TestLayerVersion(TestLayerVersionBase):
    @parameterized.expand(
        [
            ("ReferenceServerlessLayerVersionServerlessFunction"),
            ("ReferenceLambdaLayerVersionServerlessFunction"),
            ("ReferenceServerlessLayerVersionLambdaFunction"),
            ("ReferenceLambdaLayerVersionLambdaFunction"),
            ("ReferenceServerlessLayerVersionServerlessFunction"),
        ]
    )
    def test_reference_of_layer_version(self, function_logical_id):
        command_list = self.get_command_list(
            function_logical_id,
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        expected_output = '"This is a Layer Ping from simple_python"'

        self.assertEqual(process_stdout.decode("utf-8"), expected_output)

    @parameterized.expand([("OneLayerVersionServerlessFunction"), ("OneLayerVersionLambdaFunction")])
    def test_download_one_layer(self, function_logical_id):
        command_list = self.get_command_list(
            function_logical_id,
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.decode("utf-8").strip().split(os.linesep)[-1]
        expected_output = '"Layer1"'

        self.assertEqual(process_stdout, expected_output)

    @parameterized.expand([("ChangedLayerVersionServerlessFunction"), ("ChangedLayerVersionLambdaFunction")])
    def test_publish_changed_download_layer(self, function_logical_id):
        layer_name = self.layer_utils.generate_layer_name()
        self.layer_utils.upsert_layer(layer_name=layer_name, ref_layer_name="ChangedLayerArn", layer_zip="layer1.zip")

        command_list = self.get_command_list(
            function_logical_id,
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.decode("utf-8").strip().split(os.linesep)[-1]
        expected_output = '"Layer1"'

        self.assertEqual(process_stdout, expected_output)

        self.layer_utils.upsert_layer(
            layer_name=layer_name, ref_layer_name="ChangedLayerArn", layer_zip="changedlayer1.zip"
        )

        command_list = self.get_command_list(
            function_logical_id,
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate()
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.decode("utf-8").strip().split(os.linesep)[-1]
        expected_output = '"Changed_Layer_1"'

        self.assertEqual(process_stdout, expected_output)

    @parameterized.expand([("TwoLayerVersionServerlessFunction"), ("TwoLayerVersionLambdaFunction")])
    @pytest.mark.flaky(reruns=3)
    def test_download_two_layers(self, function_logical_id):

        command_list = self.get_command_list(
            function_logical_id,
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        stdout = stdout

        process_stdout = stdout.decode("utf-8").strip().split(os.linesep)[-1]
        expected_output = '"Layer2"'

        self.assertEqual(process_stdout, expected_output)

    def test_caching_two_layers(self):

        command_list = self.get_command_list(
            "TwoLayerVersionServerlessFunction",
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            layer_cache=str(self.layer_cache),
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(2, len(os.listdir(str(self.layer_cache))))

    def test_caching_two_layers_with_layer_cache_env_set(self):

        command_list = self.get_command_list(
            "TwoLayerVersionServerlessFunction",
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            parameter_overrides=self.layer_utils.parameters_overrides,
        )

        env = os.environ.copy()
        env["SAM_LAYER_CACHE_BASEDIR"] = str(self.layer_cache)

        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(2, len(os.listdir(str(self.layer_cache))))


@skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
class TestLocalZipLayerVersion(InvokeIntegBase):
    template = Path("layers", "local-zip-layer-template.yml")

    def test_local_zip_layers(
        self,
    ):
        command_list = self.get_command_list(
            "OneLayerVersionServerlessFunction",
            template_path=self.template_path,
            no_event=True,
        )

        execute = run_command(command_list)
        self.assertEqual(0, execute.process.returncode)
        self.assertEqual('"Layer1"', execute.stdout.decode())


@skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
class TestLayerVersionThatDoNotCreateCache(InvokeIntegBase):
    template = Path("layers", "layer-template.yml")
    region = "us-west-2"
    layer_utils = LayerUtils(region=region)

    def setUp(self):
        self.layer_cache = Path().home().joinpath("integ_layer_cache")

    def tearDown(self):
        docker_client = docker.from_env()
        samcli_images = docker_client.images.list(name="samcli/lambda")
        for image in samcli_images:
            docker_client.images.remove(image.id)

    def test_layer_does_not_exist(self):
        self.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerOneArn", "layer1.zip")
        non_existent_layer_arn = self.layer_utils.parameters_overrides["LayerOneArn"].replace(
            self.layer_utils.layers_meta[0].layer_name, "non_existent_layer"
        )

        command_list = self.get_command_list(
            "LayerVersionDoesNotExistFunction",
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            parameter_overrides={"NonExistentLayerArn": non_existent_layer_arn},
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()
        error_output = process_stderr.decode("utf-8")

        expected_error_output = "{} was not found.".format(non_existent_layer_arn)

        self.assertIn(expected_error_output, error_output)
        self.layer_utils.delete_layers()

    def test_account_does_not_exist_for_layer(self):
        command_list = self.get_command_list(
            "LayerVersionAccountDoesNotExistFunction",
            template_path=self.template_path,
            no_event=True,
            region=self.region,
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()
        error_output = process_stderr.decode("utf-8")

        expected_error_output = (
            "Credentials provided are missing lambda:Getlayerversion policy that is needed to "
            "download the layer or you do not have permission to download the layer"
        )

        self.assertIn(expected_error_output, error_output)


@skipIf(SKIP_LAYERS_TESTS, "Skip layers tests in Appveyor only")
class TestBadLayerVersion(InvokeIntegBase):
    template = Path("layers", "layer-bad-template.yaml")
    region = "us-west-2"

    def test_unresolved_layer_due_to_bad_instrinsic(self):
        command_list = self.get_command_list(
            "LayerBadInstrinsic",
            template_path=self.template_path,
            no_event=True,
            region=self.region,
            parameter_overrides={"LayerVersion": "1"},
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()
        error_output = process_stderr.decode("utf-8")

        expected_error_output = "Error: arn:aws:lambda:us-west-2:111111111101:layer:layerDoesNotExist:${LayerVersion} is an Invalid Layer Arn."

        self.assertIn(expected_error_output, error_output)


class TestInvokeWithFunctionFullPathToAvoidAmbiguity(InvokeIntegBase):
    template = Path("template-deep-root.yaml")

    @parameterized.expand(
        [
            ("FunctionA", {"key1": "value1", "key2": "value2", "key3": "value3"}),
            ("FunctionB", "wrote to stderr"),
            ("FunctionSomeLogicalID", "wrote to stdout"),
            ("FunctionNameC", "wrote to stdout"),
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_function_name_will_call_functions_in_top_level_stacks(self, function_identifier, expected):
        command_list = self.get_command_list(
            function_identifier, template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process_stdout.decode("utf-8")), expected)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_function_full_path_will_call_functions_in_specified_stack(self):
        command_list = self.get_command_list(
            "SubApp/SubSubApp/FunctionA", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stdout = stdout.strip()

        self.assertEqual(process.returncode, 0)
        self.assertEqual(process_stdout.decode("utf-8"), '"Hello world"')

    @pytest.mark.flaky(reruns=3)
    def test_invoke_with_non_existent_function_full_path(self):
        command_list = self.get_command_list(
            "SubApp/SubSubApp/Function404", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        process_stderr = stderr.strip()

        self.assertEqual(process.returncode, 1)
        self.assertIn("not found in template", process_stderr.decode("utf-8"))


class TestInvokeFunctionWithInlineCode(InvokeIntegBase):
    template = Path("template-inlinecode.yaml")

    @pytest.mark.flaky(reruns=3)
    def test_invoke_returncode_is_zero(self):
        command_list = self.get_command_list(
            "NoInlineCodeServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 0)

    @pytest.mark.flaky(reruns=3)
    def test_invoke_inline_code_function(self):
        command_list = self.get_command_list(
            "InlineCodeServerlessFunction", template_path=self.template_path, event_path=self.event_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise

        self.assertEqual(process.returncode, 1)
