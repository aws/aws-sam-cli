import json
import shutil
import os
import copy
from unittest import skipIf

from nose_parameterized import parameterized
from subprocess import Popen, PIPE
from timeit import default_timer as timer

import docker

from tests.integration.local.invoke.layer_utils import LayerUtils
from .invoke_integ_base import InvokeIntegBase

# Layers tests require credentials and Travis will only add credentials to the env if the PR is from the same repo.
# This is to restrict layers tests to run outside of Travis and when the branch is not master.
SKIP_LAYERS_TESTS = os.environ.get("TRAVIS", False) and os.environ.get("TRAVIS_BRANCH", "master") != "master"

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


class TestSamPython36HelloWorldIntegration(InvokeIntegBase):
    template = Path("template.yml")

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

    def test_invoke_with_env_with_aws_creds(self):
        custom_region = "my-custom-region"
        key = "key"
        secret = "secret"
        session = "session"

        command_list = self.get_command_list("EchoEnvWithParameters",
                                             template_path=self.template_path,
                                             event_path=self.event_path)

        env = copy.deepcopy(dict(os.environ))
        env["AWS_DEFAULT_REGION"] = custom_region
        env["AWS_REGION"] = custom_region
        env["AWS_ACCESS_KEY_ID"] = key
        env["AWS_SECRET_ACCESS_KEY"] = secret
        env["AWS_SESSION_TOKEN"] = session

        process = Popen(command_list, stdout=PIPE, env=env)
        process.wait()
        process_stdout = b"".join(process.stdout.readlines()).strip()
        environ = json.loads(process_stdout.decode('utf-8'))

        self.assertEquals(environ["AWS_DEFAULT_REGION"], custom_region)
        self.assertEquals(environ["AWS_REGION"], custom_region)
        self.assertEquals(environ["AWS_ACCESS_KEY_ID"], key)
        self.assertEquals(environ["AWS_SECRET_ACCESS_KEY"], secret)
        self.assertEquals(environ["AWS_SESSION_TOKEN"], session)

    def test_invoke_with_docker_network_of_host(self):
        command_list = self.get_command_list("HelloWorldServerlessFunction",
                                             template_path=self.template_path,
                                             event_path=self.event_path,
                                             docker_network='host')

        process = Popen(command_list, stdout=PIPE)
        return_code = process.wait()

        self.assertEquals(return_code, 0)


@skipIf(SKIP_LAYERS_TESTS,
        "Skip layers tests in Travis only")
class TestLayerVersion(InvokeIntegBase):
    template = Path("layers", "layer-template.yml")
    region = 'us-west-2'
    layer_utils = LayerUtils(region=region)

    def setUp(self):
        self.layer_cache = Path().home().joinpath("integ_layer_cache")

    def tearDown(self):
        docker_client = docker.from_env()
        samcli_images = docker_client.images.list(name='samcli/lambda')
        for image in samcli_images:
            docker_client.images.remove(image.id)

        shutil.rmtree(str(self.layer_cache))

    @classmethod
    def setUpClass(cls):
        cls.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerOneArn", "layer1.zip")
        cls.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerTwoArn", "layer2.zip")
        super(TestLayerVersion, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.layer_utils.delete_layers()
        super(TestLayerVersion, cls).tearDownClass()

    @parameterized.expand([
        ("ReferenceServerlessLayerVersionServerlessFunction"),
        ("ReferenceLambdaLayerVersionServerlessFunction"),
        ("ReferenceServerlessLayerVersionLambdaFunction"),
        ("ReferenceLambdaLayerVersionLambdaFunction"),
        ("ReferenceServerlessLayerVersionServerlessFunction")
    ])
    def test_reference_of_layer_version(self, function_logical_id):
        command_list = self.get_command_list(function_logical_id,
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             layer_cache=str(self.layer_cache),
                                             parameter_overrides=self.layer_utils.parameters_overrides
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()).strip()

        expected_output = '"This is a Layer Ping from simple_python"'

        self.assertEquals(process_stdout.decode('utf-8'), expected_output)

    @parameterized.expand([
        ("OneLayerVersionServerlessFunction"),
        ("OneLayerVersionLambdaFunction")
    ])
    def test_download_one_layer(self, function_logical_id):
        command_list = self.get_command_list(function_logical_id,
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             layer_cache=str(self.layer_cache),
                                             parameter_overrides=self.layer_utils.parameters_overrides
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()[-1:]).strip()
        expected_output = '"Layer1"'

        self.assertEquals(process_stdout.decode('utf-8'), expected_output)

    @parameterized.expand([
        ("ChangedLayerVersionServerlessFunction"),
        ("ChangedLayerVersionLambdaFunction")
    ])
    def test_publish_changed_download_layer(self, function_logical_id):
        layer_name = self.layer_utils.generate_layer_name()
        self.layer_utils.upsert_layer(layer_name=layer_name,
                                      ref_layer_name="ChangedLayerArn",
                                      layer_zip="layer1.zip")

        command_list = self.get_command_list(function_logical_id,
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             layer_cache=str(self.layer_cache),
                                             parameter_overrides=self.layer_utils.parameters_overrides
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()[-1:]).strip()
        expected_output = '"Layer1"'

        self.assertEquals(process_stdout.decode('utf-8'), expected_output)

        self.layer_utils.upsert_layer(layer_name=layer_name,
                                      ref_layer_name="ChangedLayerArn",
                                      layer_zip="changedlayer1.zip")

        command_list = self.get_command_list(function_logical_id,
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             layer_cache=str(self.layer_cache),
                                             parameter_overrides=self.layer_utils.parameters_overrides
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        process_stdout = b"".join(process.stdout.readlines()[-1:]).strip()
        expected_output = '"Changed_Layer_1"'

        self.assertEquals(process_stdout.decode('utf-8'), expected_output)

    @parameterized.expand([
        ("TwoLayerVersionServerlessFunction"),
        ("TwoLayerVersionLambdaFunction")
    ])
    def test_download_two_layers(self, function_logical_id):

        command_list = self.get_command_list(function_logical_id,
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             layer_cache=str(self.layer_cache),
                                             parameter_overrides=self.layer_utils.parameters_overrides
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        stdout = process.stdout.readlines()

        process_stdout = b"".join(stdout[-1:]).strip()
        expected_output = '"Layer2"'

        self.assertEquals(process_stdout.decode('utf-8'), expected_output)

    def test_caching_two_layers(self):

        command_list = self.get_command_list("TwoLayerVersionServerlessFunction",
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             layer_cache=str(self.layer_cache),
                                             parameter_overrides=self.layer_utils.parameters_overrides
                                             )

        process = Popen(command_list, stdout=PIPE)
        process.wait()

        self.assertEquals(2, len(os.listdir(str(self.layer_cache))))


@skipIf(SKIP_LAYERS_TESTS,
        "Skip layers tests in Travis only")
class TestLayerVersionThatDoNotCreateCache(InvokeIntegBase):
    template = Path("layers", "layer-template.yml")
    region = 'us-west-2'
    layer_utils = LayerUtils(region=region)

    def setUp(self):
        self.layer_cache = Path().home().joinpath("integ_layer_cache")

    def tearDown(self):
        docker_client = docker.from_env()
        samcli_images = docker_client.images.list(name='samcli/lambda')
        for image in samcli_images:
            docker_client.images.remove(image.id)

    def test_layer_does_not_exist(self):
        self.layer_utils.upsert_layer(LayerUtils.generate_layer_name(), "LayerOneArn", "layer1.zip")
        non_existent_layer_arn = self.layer_utils.parameters_overrides["LayerOneArn"].replace(
            self.layer_utils.layers_meta[0].layer_name, 'non_existent_layer')

        command_list = self.get_command_list("LayerVersionDoesNotExistFunction",
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region,
                                             parameter_overrides={
                                                 'NonExistentLayerArn': non_existent_layer_arn
                                             }
                                             )

        process = Popen(command_list, stderr=PIPE)
        process.wait()

        process_stderr = b"".join(process.stderr.readlines()).strip()
        error_output = process_stderr.decode('utf-8')

        expected_error_output = "{} was not found.".format(non_existent_layer_arn)

        self.assertIn(expected_error_output, error_output)
        self.layer_utils.delete_layers()

    def test_account_does_not_exist_for_layer(self):
        command_list = self.get_command_list("LayerVersionAccountDoesNotExistFunction",
                                             template_path=self.template_path,
                                             no_event=True,
                                             region=self.region
                                             )

        process = Popen(command_list, stderr=PIPE)
        process.wait()

        process_stderr = b"".join(process.stderr.readlines()).strip()
        error_output = process_stderr.decode('utf-8')

        expected_error_output = "Credentials provided are missing lambda:Getlayerversion policy that is needed to " \
                                "download the layer or you do not have permission to download the layer"

        self.assertIn(expected_error_output, error_output)
