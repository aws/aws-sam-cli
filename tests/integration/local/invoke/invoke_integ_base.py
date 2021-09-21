import os
import shutil
import tempfile
import uuid
from typing import Optional
from unittest import TestCase, skipIf
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired

from tests.cdk_testing_utils import CdkPythonEnv
from tests.testing_utils import SKIP_DOCKER_MESSAGE, SKIP_DOCKER_TESTS

TIMEOUT = 300


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class InvokeIntegBase(TestCase):
    template: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata")
        cls.template_path = str(cls.test_data_path.joinpath("invoke", cls.template))
        cls.event_path = str(cls.test_data_path.joinpath("invoke", "event.json"))
        cls.event_utf8_path = str(cls.test_data_path.joinpath("invoke", "event_utf8.json"))
        cls.env_var_path = str(cls.test_data_path.joinpath("invoke", "vars.json"))

    @staticmethod
    def get_integ_dir():
        return Path(__file__).resolve().parents[2]

    @property
    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_command_list(
        self,
        function_to_invoke,
        template_path=None,
        event_path=None,
        env_var_path=None,
        parameter_overrides=None,
        region=None,
        no_event=None,
        profile=None,
        layer_cache=None,
        docker_network=None,
    ):
        command_list = [self.base_command, "local", "invoke", function_to_invoke]

        if template_path:
            command_list = command_list + ["-t", template_path]

        if event_path:
            command_list = command_list + ["-e", event_path]

        if env_var_path:
            command_list = command_list + ["-n", env_var_path]

        if no_event:
            command_list = command_list + ["--no-event"]

        if profile:
            command_list = command_list + ["--profile", profile]

        if layer_cache:
            command_list = command_list + ["--layer-cache-basedir", layer_cache]

        if docker_network:
            command_list = command_list + ["--docker-network", docker_network]

        if parameter_overrides:
            arg_value = " ".join(
                ["ParameterKey={},ParameterValue={}".format(key, value) for key, value in parameter_overrides.items()]
            )
            command_list = command_list + ["--parameter-overrides", arg_value]

        if region:
            command_list = command_list + ["--region", region]

        return command_list

    def get_build_command_list(
        self,
        template_path=None,
        cached=None,
        parallel=None,
        use_container=None,
    ):
        command_list = [self.base_command, "build"]

        if template_path:
            command_list = command_list + ["-t", template_path]

        if cached:
            command_list = command_list + ["-c"]

        if parallel:
            command_list = command_list + ["-p"]

        if use_container:
            command_list = command_list + ["-u"]

        return command_list

    def run_command(self, command_list, env=None):
        process = Popen(command_list, stdout=PIPE, env=env)
        try:
            (stdout, stderr) = process.communicate(timeout=TIMEOUT)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class CDKInvokeIntegBase(InvokeIntegBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scratch_dir = str(Path(__file__).resolve().parent.joinpath(str(uuid.uuid4()).replace("-", "")[:10]))
        os.mkdir(cls.scratch_dir)

    @classmethod
    def tearDownClass(cls):
        cls.scratch_dir and shutil.rmtree(cls.scratch_dir, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        # Sythensizing a CDK app produces a Cloud Assembly. To simulate an actual working setup, we copy the CDK app
        # from test_data to a scratch dir as if the scratch dir is the working directory.
        # This is similar to the setup in BuildIntegBase
        # shutil.rmtree(self.scratch_dir, ignore_errors=True)
        # os.mkdir(self.scratch_dir)
        self.working_dir = tempfile.mkdtemp(dir=self.scratch_dir)

    def tearDown(self):
        self.working_dir and shutil.rmtree(self.working_dir, ignore_errors=True)

    def get_command_list(
        self,
        function_to_invoke,
        template_path=None,
        event_path=None,
        env_var_path=None,
        parameter_overrides=None,
        region=None,
        no_event=None,
        profile=None,
        layer_cache=None,
        docker_network=None,
        project_type="CDK",
    ):
        command_list = super().get_command_list(
            function_to_invoke,
            template_path=template_path,
            event_path=event_path,
            env_var_path=env_var_path,
            parameter_overrides=parameter_overrides,
            region=region,
            no_event=no_event,
            profile=profile,
            layer_cache=layer_cache,
            docker_network=docker_network,
        )

        if project_type:
            command_list = command_list + ["--project-type", str(project_type)]

        return command_list


@skipIf(SKIP_DOCKER_TESTS, SKIP_DOCKER_MESSAGE)
class CDKInvokeIntegPythonBase(CDKInvokeIntegBase):
    @classmethod
    def setUpClass(cls):
        cls.template = ""
        super().setUpClass()
        cls.template_path = str(cls.test_data_path.joinpath("invoke", cls.template))
        cls.test_data_path = cls.get_integ_dir().joinpath("testdata", "invoke")
        cls.event_path = str(cls.test_data_path.joinpath("cdk", "python", "event.json"))
        cls.event_utf8_path = str(cls.test_data_path.joinpath("cdk", "python", "event_utf8.json"))
        cls.env_var_path = str(cls.test_data_path.joinpath("cdk", "python", "vars.json"))
        cls.cdk_python_env = CdkPythonEnv(cls.scratch_dir)
        cls.cdk_python_env.install_dependencies(str(cls.test_data_path.joinpath("cdk", "python", "requirements.txt")))
