import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest import TestCase
from unittest.mock import patch, ANY

import botocore.exceptions
import click
from click.testing import CliRunner

from samcli.commands.exceptions import UserException
from samcli.commands.init import cli as init_cmd
from samcli.commands.init import do_cli as init_cli
from samcli.commands.init.init_templates import InitTemplates, APP_TEMPLATES_REPO_URL
from samcli.lib.init import GenerateProjectFailedError
from samcli.lib.utils import osutils
from samcli.lib.utils.git_repo import GitRepo
from samcli.lib.utils.packagetype import IMAGE, ZIP


class MockInitTemplates:
    def __init__(self, no_interactive=False):
        self._no_interactive = no_interactive
        self._git_repo: GitRepo = GitRepo(
            url=APP_TEMPLATES_REPO_URL,
        )
        self._git_repo.clone_attempted = True
        self._git_repo.local_path = Path("repository")


class TestCli(TestCase):
    def setUp(self):
        self.ctx = None
        self.no_interactive = True
        self.location = None
        self.pt_explicit = True
        self.package_type = ZIP
        self.runtime = "python3.6"
        self.base_image = None
        self.dependency_manager = "pip"
        self.output_dir = "."
        self.name = "testing project"
        self.app_template = "hello-world"
        self.no_input = False
        self.extra_context = '{"project_name": "testing project", "runtime": "python3.6"}'
        self.extra_context_as_json = {"project_name": "testing project", "runtime": "python3.6"}

    # setup cache for clone, so that if `git clone` is called multiple times on the same URL,
    # only one clone will happen.
    clone_cache: Dict[str, Path]
    patcher: Any

    @classmethod
    def setUpClass(cls) -> None:
        # Make (url -> directory) cache to avoid cloning the same thing twice
        cls.clone_cache = {}
        cls.patcher = patch("samcli.lib.utils.git_repo.check_output", side_effect=cls.check_output_mock)
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.patcher.stop()
        for _, directory in cls.clone_cache.items():
            shutil.rmtree(directory.parent)

    @classmethod
    def check_output_mock(cls, commands, cwd, stderr):
        git_executable, _, url, clone_name = commands
        if url not in cls.clone_cache:
            tempdir = tempfile.NamedTemporaryFile(delete=False).name
            subprocess.check_output(
                [git_executable, "clone", url, clone_name],
                cwd=tempdir,
                stderr=stderr,
            )
            cls.clone_cache[url] = Path(tempdir, clone_name)

        osutils.copytree(str(cls.clone_cache[url]), str(Path(cwd, clone_name)))

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli(self, generate_project_patch, git_repo_clone_mock):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=self.runtime,
            base_image=self.base_image,
            dependency_manager=self.dependency_manager,
            output_dir=None,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            extra_context=None,
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            ZIP,
            self.runtime,
            self.dependency_manager,
            self.output_dir,
            self.name,
            True,
            self.extra_context_as_json,
        )

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_image_cli(self, generate_project_patch, git_repo_clone_mock):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=IMAGE,
            runtime=None,
            base_image="amazon/nodejs12.x-base",
            dependency_manager="npm",
            output_dir=None,
            name=self.name,
            app_template=None,
            no_input=self.no_input,
            extra_context=None,
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            IMAGE,
            "nodejs12.x",
            "npm",
            self.output_dir,
            self.name,
            True,
            {"runtime": "nodejs12.x", "project_name": "testing project"},
        )

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_image_java_cli(self, generate_project_patch, git_repo_clone_mock):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=IMAGE,
            runtime=None,
            base_image="amazon/java11-base",
            dependency_manager="maven",
            output_dir=None,
            name=self.name,
            app_template=None,
            no_input=self.no_input,
            extra_context=None,
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            IMAGE,
            "java11",
            "maven",
            self.output_dir,
            self.name,
            True,
            {"runtime": "java11", "project_name": "testing project"},
        )

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    def test_init_fails_invalid_template(self, git_repo_clone_mock):
        # WHEN an unknown app template is passed in
        # THEN an exception should be raised
        with self.assertRaises(UserException):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                location=self.location,
                pt_explicit=self.pt_explicit,
                package_type=self.package_type,
                runtime=self.runtime,
                base_image=self.base_image,
                dependency_manager=self.dependency_manager,
                output_dir=None,
                name=self.name,
                app_template="wrong-and-bad",
                no_input=self.no_input,
                extra_context=None,
            )

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    def test_init_fails_invalid_dep_mgr(self, git_repo_clone_mock):
        # WHEN an unknown app template is passed in
        # THEN an exception should be raised
        with self.assertRaises(UserException):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                location=self.location,
                pt_explicit=self.pt_explicit,
                package_type=self.package_type,
                runtime=self.runtime,
                base_image=self.base_image,
                dependency_manager="bad-wrong",
                output_dir=None,
                name=self.name,
                app_template=self.app_template,
                no_input=self.no_input,
                extra_context=None,
            )

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_generate_project_fails(self, generate_project_patch, git_repo_clone_mock):
        # GIVEN generate_project fails to create a project
        generate_project_patch.side_effect = GenerateProjectFailedError(
            project=self.name, provider_error="Something wrong happened"
        )

        # WHEN generate_project returns an error
        # THEN we should receive a GenerateProjectFailedError Exception
        with self.assertRaises(UserException):
            init_cli(
                self.ctx,
                no_interactive=self.no_interactive,
                location="self.location",
                pt_explicit=self.pt_explicit,
                package_type=self.package_type,
                runtime=self.runtime,
                base_image=self.base_image,
                dependency_manager=self.dependency_manager,
                output_dir=self.output_dir,
                name=self.name,
                app_template=None,
                no_input=self.no_input,
                extra_context=None,
            )

            generate_project_patch.assert_called_with(
                self.location, self.runtime, self.dependency_manager, self.output_dir, self.name, self.no_input
            )

    @patch("samcli.lib.utils.git_repo.GitRepo.clone")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_generate_project_image_fails(self, generate_project_patch, git_repo_clone_mock):
        # GIVEN generate_project fails to create a project
        generate_project_patch.side_effect = GenerateProjectFailedError(
            project=self.name, provider_error="Something wrong happened"
        )

        # WHEN generate_project returns an error
        # THEN we should receive a GenerateProjectFailedError Exception
        with self.assertRaises(UserException):
            init_cli(
                self.ctx,
                no_interactive=self.no_interactive,
                location=self.location,
                pt_explicit=self.pt_explicit,
                package_type=IMAGE,
                runtime=None,
                base_image="python3.6-base",
                dependency_manager="wrong-dependency-manager",
                output_dir=self.output_dir,
                name=self.name,
                app_template=None,
                no_input=self.no_input,
                extra_context=None,
            )

            generate_project_patch.assert_called_with(
                self.location, self.runtime, self.dependency_manager, self.output_dir, self.name, self.no_input
            )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_parameter_not_passed(self, generate_project_patch):
        # GIVEN no extra_context parameter passed
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=self.runtime,
            base_image=self.base_image,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            extra_context=None,
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            ANY, ZIP, self.runtime, self.dependency_manager, ".", self.name, True, self.extra_context_as_json
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_parameter_passed(self, generate_project_patch):
        # GIVEN extra_context and default_parameter(name, runtime)
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=self.runtime,
            base_image=self.base_image,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            extra_context='{"schema_name":"events", "schema_type":"aws"}',
        )

        # THEN we should receive no errors and right extra_context should be passed
        generate_project_patch.assert_called_once_with(
            ANY,
            ZIP,
            self.runtime,
            self.dependency_manager,
            ".",
            self.name,
            True,
            {"project_name": "testing project", "runtime": "python3.6", "schema_name": "events", "schema_type": "aws"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_not_overriding_default_parameter(self, generate_project_patch):
        # GIVEN default_parameters(name, runtime) and extra_context trying to override default parameter
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=self.runtime,
            base_image=self.base_image,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            extra_context='{"project_name": "my_project", "runtime": "java8", "schema_name":"events", "schema_type": "aws"}',
        )

        # THEN extra_context should have not overridden default_parameters(name, runtime)
        generate_project_patch.assert_called_once_with(
            ANY,
            ZIP,
            self.runtime,
            self.dependency_manager,
            ".",
            self.name,
            True,
            {"project_name": "testing project", "runtime": "python3.6", "schema_name": "events", "schema_type": "aws"},
        )

    def test_init_cli_with_extra_context_input_as_wrong_json_raises_exception(self):
        # GIVEN extra_context as wrong json
        # WHEN a sam init is called
        with self.assertRaises(click.UsageError):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                location=self.location,
                pt_explicit=self.pt_explicit,
                package_type=self.package_type,
                runtime=self.runtime,
                base_image=self.base_image,
                dependency_manager=self.dependency_manager,
                output_dir=self.output_dir,
                name=self.name,
                app_template=self.app_template,
                no_input=self.no_input,
                extra_context='{"project_name", "my_project", "runtime": "java8", "schema_name":"events", "schema_type": "aws"}',
            )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_must_set_default_context_when_location_is_provided(self, generate_project_patch):
        # GIVEN default_parameter(name, runtime) with location
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location="custom location",
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime="java8",
            base_image=self.base_image,
            dependency_manager=None,
            output_dir=self.output_dir,
            name="test-project",
            app_template=None,
            no_input=None,
            extra_context='{"schema_name":"events", "schema_type": "aws"}',
        )

        # THEN should set default parameter(name, runtime) as extra_context
        generate_project_patch.assert_called_once_with(
            "custom location",
            ZIP,
            "java8",
            None,
            ".",
            "test-project",
            None,
            {"schema_name": "events", "schema_type": "aws", "runtime": "java8", "project_name": "test-project"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_must_only_set_passed_project_name_when_location_is_provided(self, generate_project_patch):
        # GIVEN only name and extra_context
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location="custom location",
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=None,
            base_image=self.base_image,
            dependency_manager=None,
            output_dir=self.output_dir,
            name="test-project",
            app_template=None,
            no_input=None,
            extra_context='{"schema_name":"events", "schema_type": "aws"}',
        )

        # THEN extra_context should be without runtime
        generate_project_patch.assert_called_once_with(
            "custom location",
            ZIP,
            None,
            None,
            ".",
            "test-project",
            None,
            {"schema_name": "events", "schema_type": "aws", "project_name": "test-project"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_must_only_set_passed_runtime_when_location_is_provided(self, generate_project_patch):
        # GIVEN only runtime and extra_context
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location="custom location",
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime="java8",
            base_image=self.base_image,
            dependency_manager=None,
            output_dir=self.output_dir,
            name=None,
            app_template=None,
            no_input=None,
            extra_context='{"schema_name":"events", "schema_type": "aws"}',
        )

        # THEN extra_context should be without name
        generate_project_patch.assert_called_once_with(
            "custom location",
            ZIP,
            "java8",
            None,
            ".",
            None,
            None,
            {"schema_name": "events", "schema_type": "aws", "runtime": "java8"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_parameter_passed_as_escaped(self, generate_project_patch):
        # GIVEN extra_context and default_parameter(name, runtime)
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=self.runtime,
            base_image=self.base_image,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            # fmt: off
            extra_context='{\"schema_name\":\"events\", \"schema_type\":\"aws\"}',
            # fmt: on
        )

        # THEN we should receive no errors and right extra_context should be passed
        generate_project_patch.assert_called_once_with(
            ANY,
            ZIP,
            self.runtime,
            self.dependency_manager,
            ".",
            self.name,
            True,
            {"project_name": "testing project", "runtime": "python3.6", "schema_name": "events", "schema_type": "aws"},
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("samcli.commands.init.interactive_init_flow.do_extract_and_merge_schemas_code")
    @patch("samcli.commands.init.interactive_event_bridge_flow.SchemasApiCaller")
    @patch("samcli.commands.init.interactive_event_bridge_flow.get_schemas_client")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_with_event_bridge_app_template(
        self,
        generate_project_patch,
        get_schemas_client_mock,
        schemas_api_caller_mock,
        do_extract_and_merge_schemas_code_mock,
        session_mock,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "java8/cookiecutter-aws-sam-hello-java-maven",
                "displayName": "Hello World Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world",
            },
            {
                "directory": "java8/cookiecutter-aws-sam-eventbridge-schema-app-java-maven",
                "displayName": "Hello World Schema example Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "eventBridge-schema-app",
                "isDynamicTemplate": "True",
            },
        ]
        session_mock.return_value.profile_name = "test"
        session_mock.return_value.region_name = "ap-northeast-1"
        schemas_api_caller_mock.return_value.list_registries.return_value = {
            "registries": ["aws.events", "default"],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.list_schemas.return_value = {
            "schemas": [
                "aws.autoscaling.AWSAPICallViaCloudTrail",
                "aws.autoscaling.EC2InstanceLaunchSuccessful",
                "aws.autoscaling.EC2InstanceLaunchUnsuccessful",
                "aws.autoscaling.EC2InstanceTerminateLifecycleAction",
                "aws.autoscaling.EC2InstanceTerminateSuccessful",
                "aws.autoscaling.EC2InstanceTerminateUnsuccessful",
            ],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.get_latest_schema_version.return_value = "1"
        schemas_api_caller_mock.return_value.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "AWSAPICallViaCloudTrail",
            "schemas_package_hierarchy": "schemas.aws.AWSAPICallViaCloudTrail",
        }
        schemas_api_caller_mock.return_value.download_source_code_binding.return_value = "result.zip"
        # WHEN the user follows interactive init prompts

        # 1: AWS Quick Start Templates
        # 5: Java Runtime
        # 1: dependency manager maven
        # test-project: response to name
        # Y: Don't clone/update the source repo
        # 2: select event-bridge app from scratch
        # Y: Use default aws configuration
        # 1: select aws.events as registries
        # 1: select schema AWSAPICallViaCloudTrail
        user_input = """
1
1
5
1
test-project
Y
2
Y
1
1
.
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            ANY,
            ZIP,
            "java11",
            "maven",
            ".",
            "test-project",
            True,
            {
                "project_name": "test-project",
                "runtime": "java11",
                "AWS_Schema_registry": "aws.events",
                "AWS_Schema_name": "AWSAPICallViaCloudTrail",
                "AWS_Schema_source": "aws.autoscaling",
                "AWS_Schema_detail_type": "aws.autoscaling response",
                "AWS_Schema_root": "schemas.aws.AWSAPICallViaCloudTrail",
            },
        )
        get_schemas_client_mock.assert_called_once_with(None, "ap-northeast-1")
        do_extract_and_merge_schemas_code_mock.do_extract_and_merge_schemas_code_mock(
            "result.zip", ".", "test-project", ANY
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_with_image_app_template(
        self,
        generate_project_patch,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "java8-base/cookiecutter-aws-sam-hello-java-maven-lambda-image",
                "displayName": "Hello World Lambda Image Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world-lambda-image",
            }
        ]

        # WHEN the user follows interactive init prompts

        # 1: AWS Quick Start Templates
        # 2: Package type - Image
        # 14: Java8 base image
        # 1: dependency manager maven
        # test-project: response to name

        user_input = """
1
2
14
1
test-project
            """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        generate_project_patch.assert_called_once_with(
            ANY,
            IMAGE,
            "java8",
            "maven",
            ".",
            "test-project",
            True,
            {"project_name": "test-project", "runtime": "java8"},
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("samcli.commands.init.interactive_init_flow.do_extract_and_merge_schemas_code")
    @patch("samcli.commands.init.interactive_event_bridge_flow.SchemasApiCaller")
    @patch("samcli.commands.init.interactive_event_bridge_flow.get_schemas_client")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_with_event_bridge_app_template_and_aws_configuration(
        self,
        generate_project_patch,
        get_schemas_client_mock,
        schemas_api_caller_mock,
        do_extract_and_merge_schemas_code_mock,
        session_mock,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "java8/cookiecutter-aws-sam-hello-java-maven",
                "displayName": "Hello World Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world",
            },
            {
                "directory": "java8/cookiecutter-aws-sam-eventbridge-schema-app-java-maven",
                "displayName": "Hello World Schema example Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "eventBridge-schema-app",
                "isDynamicTemplate": "True",
            },
        ]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "ap-south-1"
        session_mock.return_value.available_profiles = ["default", "test-profile"]
        session_mock.return_value.get_available_regions.return_value = ["ap-south-2", "us-east-1"]
        schemas_api_caller_mock.return_value.list_registries.return_value = {
            "registries": ["aws.events"],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.list_schemas.return_value = {
            "schemas": [
                "aws.autoscaling.AWSAPICallViaCloudTrail",
                "aws.autoscaling.EC2InstanceLaunchSuccessful",
                "aws.autoscaling.EC2InstanceLaunchUnsuccessful",
                "aws.autoscaling.EC2InstanceTerminateLifecycleAction",
                "aws.autoscaling.EC2InstanceTerminateSuccessful",
                "aws.autoscaling.EC2InstanceTerminateUnsuccessful",
            ],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.get_latest_schema_version.return_value = "1"
        schemas_api_caller_mock.return_value.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "AWSAPICallViaCloudTrail",
            "schemas_package_hierarchy": "schemas.aws.AWSAPICallViaCloudTrail",
        }
        schemas_api_caller_mock.return_value.download_source_code_binding.return_value = "result.zip"
        # WHEN the user follows interactive init prompts

        # 1: AWS Quick Start Templates
        # 5: Java Runtime
        # 1: dependency manager maven
        # test-project: response to name
        # Y: Don't clone/update the source repo
        # 2: select event-bridge app from scratch
        # N: Use default AWS profile
        # 1: Select profile
        # us-east-1: Select region
        # 1: select aws.events as registries
        # 1: select schema AWSAPICallViaCloudTrail
        user_input = """
1
1
5
1
test-project
Y
2
N
1
us-east-1
1
1
.
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            ANY,
            ZIP,
            "java11",
            "maven",
            ".",
            "test-project",
            True,
            {
                "project_name": "test-project",
                "runtime": "java11",
                "AWS_Schema_registry": "aws.events",
                "AWS_Schema_name": "AWSAPICallViaCloudTrail",
                "AWS_Schema_source": "aws.autoscaling",
                "AWS_Schema_detail_type": "aws.autoscaling response",
                "AWS_Schema_root": "schemas.aws.AWSAPICallViaCloudTrail",
            },
        )
        get_schemas_client_mock.assert_called_once_with("default", "us-east-1")
        do_extract_and_merge_schemas_code_mock.do_extract_and_merge_schemas_code("result.zip", ".", "test-project", ANY)

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("samcli.commands.init.interactive_event_bridge_flow.SchemasApiCaller")
    @patch("samcli.commands.init.interactive_event_bridge_flow.get_schemas_client")
    def test_init_cli_int_with_event_bridge_app_template_and_aws_configuration_with_wrong_region_name(
        self, get_schemas_client_mock, schemas_api_caller_mock, session_mock, init_options_from_manifest_mock
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "java8/cookiecutter-aws-sam-hello-java-maven",
                "displayName": "Hello World Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world",
            },
            {
                "directory": "java8/cookiecutter-aws-sam-eventbridge-schema-app-java-maven",
                "displayName": "Hello World Schema example Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "eventBridge-schema-app",
                "isDynamicTemplate": "True",
            },
        ]
        session_mock.return_value.profile_name = "default"
        session_mock.return_value.region_name = "ap-south-1"
        session_mock.return_value.available_profiles = ["default", "test-profile"]
        session_mock.return_value.get_available_regions.return_value = ["ap-south-2", "us-east-1"]
        schemas_api_caller_mock.return_value.list_registries.side_effect = botocore.exceptions.EndpointConnectionError(
            endpoint_url="Not valid endpoint."
        )
        # WHEN the user follows interactive init prompts

        # 1: AWS Quick Start Templates
        # 5: Java Runtime
        # 1: dependency manager maven
        # test-project: response to name
        # Y: Don't clone/update the source repo
        # 2: select event-bridge app from scratch
        # N: Use default AWS profile
        # 1: Select profile
        # invalid-region: Select region
        # 1: select aws.events as registries
        # 1: select schema AWSAPICallViaCloudTrail
        user_input = """
1
1
5
1
test-project
Y
2
N
1
invalid-region
1
1
.
            """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        self.assertTrue(result.exception)
        get_schemas_client_mock.assert_called_once_with("default", "invalid-region")

    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("samcli.commands.init.interactive_init_flow.do_extract_and_merge_schemas_code")
    @patch("samcli.commands.init.interactive_event_bridge_flow.SchemasApiCaller")
    @patch("samcli.commands.init.interactive_event_bridge_flow.get_schemas_client")
    @patch("samcli.commands.init.init_generator.generate_project")
    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    def test_init_cli_int_with_download_manager_raises_exception(
        self,
        generate_project_patch,
        get_schemas_client_mock,
        schemas_api_caller_mock,
        do_extract_and_merge_schemas_code_mock,
        session_mock,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "java8/cookiecutter-aws-sam-hello-java-maven",
                "displayName": "Hello World Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world",
            },
            {
                "directory": "java8/cookiecutter-aws-sam-eventbridge-schema-app-java-maven",
                "displayName": "Hello World Schema example Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "eventBridge-schema-app",
                "isDynamicTemplate": "True",
            },
        ]
        session_mock.return_value.profile_name = "test"
        session_mock.return_value.region_name = "ap-northeast-1"
        schemas_api_caller_mock.return_value.list_registries.return_value = {
            "registries": ["aws.events", "default", "test-registries"],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.list_schemas.return_value = {
            "schemas": [
                "aws.autoscaling.AWSAPICallViaCloudTrail",
                "aws.autoscaling.EC2InstanceLaunchSuccessful",
                "aws.autoscaling.EC2InstanceLaunchUnsuccessful",
                "aws.autoscaling.EC2InstanceTerminateLifecycleAction",
                "aws.autoscaling.EC2InstanceTerminateSuccessful",
                "aws.autoscaling.EC2InstanceTerminateUnsuccessful",
            ],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.get_latest_schema_version.return_value = "1"
        schemas_api_caller_mock.return_value.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "AWSAPICallViaCloudTrail",
            "schemas_package_hierarchy": "schemas.aws.AWSAPICallViaCloudTrail",
        }
        schemas_api_caller_mock.return_value.download_source_code_binding.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ConflictException", "Message": "ConflictException"}}, "operation"
        )
        # WHEN the user follows interactive init prompts

        # 1: AWS Quick Start Templates
        # 5: Java Runtime
        # 1: dependency manager maven
        # test-project: response to name
        # Y: Don't clone/update the source repo
        # 2: select event-bridge app from scratch
        # Y: Don't override aws configuration
        # 1: select aws.events as registries
        # 1: select schema AWSAPICallViaCloudTrail
        user_input = """
1
1
5
1
test-project
Y
2
Y
1
1
.
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)
        self.assertTrue(result.exception)
        generate_project_patch.assert_called_once_with(
            ANY,
            ZIP,
            "java11",
            "maven",
            ".",
            "test-project",
            True,
            {
                "project_name": "test-project",
                "runtime": "java11",
                "AWS_Schema_registry": "aws.events",
                "AWS_Schema_name": "AWSAPICallViaCloudTrail",
                "AWS_Schema_source": "aws.autoscaling",
                "AWS_Schema_detail_type": "aws.autoscaling response",
                "AWS_Schema_root": "schemas.aws.AWSAPICallViaCloudTrail",
            },
        )
        get_schemas_client_mock.assert_called_once_with(None, "ap-northeast-1")
        do_extract_and_merge_schemas_code_mock.do_extract_and_merge_schemas_code_mock(
            "result.zip", ".", "test-project", ANY
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.lib.schemas.schemas_aws_config.Session")
    @patch("samcli.commands.init.interactive_init_flow.do_extract_and_merge_schemas_code")
    @patch("samcli.commands.init.interactive_event_bridge_flow.SchemasApiCaller")
    @patch("samcli.commands.init.interactive_event_bridge_flow.get_schemas_client")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_with_schemas_details_raises_exception(
        self,
        generate_project_patch,
        get_schemas_client_mock,
        schemas_api_caller_mock,
        do_extract_and_merge_schemas_code_mock,
        session_mock,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "java8/cookiecutter-aws-sam-hello-java-maven",
                "displayName": "Hello World Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "hello-world",
            },
            {
                "directory": "java8/cookiecutter-aws-sam-eventbridge-schema-app-java-maven",
                "displayName": "Hello World Schema example Example: Maven",
                "dependencyManager": "maven",
                "appTemplate": "eventBridge-schema-app",
                "isDynamicTemplate": "True",
            },
        ]
        session_mock.return_value.profile_name = "test"
        session_mock.return_value.region_name = "ap-northeast-1"
        schemas_api_caller_mock.return_value.list_registries.return_value = {
            "registries": ["aws.events"],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.list_schemas.return_value = {
            "schemas": [
                "aws.autoscaling.AWSAPICallViaCloudTrail",
                "aws.autoscaling.EC2InstanceLaunchSuccessful",
                "aws.autoscaling.EC2InstanceLaunchUnsuccessful",
                "aws.autoscaling.EC2InstanceTerminateLifecycleAction",
                "aws.autoscaling.EC2InstanceTerminateSuccessful",
                "aws.autoscaling.EC2InstanceTerminateUnsuccessful",
            ],
            "next_token": None,
        }
        schemas_api_caller_mock.return_value.get_latest_schema_version.return_value = "1"
        schemas_api_caller_mock.return_value.get_schema_metadata.side_effect = botocore.exceptions.ClientError(
            {"Error": {"Code": "ConflictException", "Message": "ConflictException"}}, "operation"
        )
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 5: Java Runtime
        # 1: dependency manager maven
        # test-project: response to name
        # Y: Don't clone/update the source repo
        # 2: select event-bridge app from scratch
        # Y: Used default aws configuration
        # 1: select aws.events as registries
        # 1: select schema AWSAPICallViaCloudTrail
        user_input = """
1
1
5
1
test-project
Y
2
Y
1
1
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)
        self.assertTrue(result.exception)
        get_schemas_client_mock.assert_called_once_with(None, "ap-northeast-1")
        assert not generate_project_patch.called
        assert not do_extract_and_merge_schemas_code_mock.called

    @patch("samcli.commands.init.init_templates.InitTemplates.location_from_app_template")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_passes_dynamic_event_bridge_template(self, generate_project_patch, location_from_app_template_mock):
        location_from_app_template_mock.return_value = "applocation"
        # WHEN dynamic event bridge template is passed in non-interactive mode.
        init_cli(
            ctx=self.ctx,
            no_interactive=True,
            location=self.location,
            pt_explicit=self.pt_explicit,
            package_type=self.package_type,
            runtime=self.runtime,
            base_image=self.base_image,
            dependency_manager=self.dependency_manager,
            output_dir=None,
            name=self.name,
            app_template="eventBridge-schema-app",
            no_input=self.no_input,
            extra_context=None,
        )

        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            ZIP,
            self.runtime,
            self.dependency_manager,
            self.output_dir,
            self.name,
            True,
            self.extra_context_as_json,
        )

    @patch("samcli.lib.utils.git_repo.GitRepo._ensure_clone_directory_exists")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_from_location(self, generate_project_patch, cd_mock):
        # WHEN the user follows interactive init prompts

        # 2: selecting custom location
        # foo: the "location"
        user_input = """
2
foo
        """

        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        # THEN we should receive no errors
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            "foo",
            ZIP,
            None,
            None,
            ".",
            None,
            False,
            None,
        )

    @patch("samcli.lib.utils.git_repo.GitRepo._ensure_clone_directory_exists")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_no_package_type(self, generate_project_patch, cd_mock):
        # WHEN the user follows interactive init prompts

        # 1: selecting template source
        # 2s: selecting package type
        user_input = """
1
2
1
        """
        args = [
            "--no-input",
            "--name",
            "untitled6",
            "--base-image",
            "amazon/python3.8-base",
            "--dependency-manager",
            "pip",
        ]
        runner = CliRunner()
        result = runner.invoke(init_cmd, args=args, input=user_input)

        # THEN we should receive no errors
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            ANY,
            IMAGE,
            "python3.8",
            "pip",
            ".",
            "untitled6",
            True,
            ANY,
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    def test_init_cli_image_pool_with_base_image_having_multiple_managed_template_but_no_app_template_provided(
        self,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "python3.8-image/cookiecutter-aws-sam-hello-python-lambda-image",
                "displayName": "Hello World Lambda Image Example",
                "dependencyManager": "pip",
                "appTemplate": "hello-world-lambda-image",
                "packageType": "Image",
            },
            {
                "directory": "python3.8-image/cookiecutter-ml-apigw-pytorch",
                "displayName": "PyTorch Machine Learning Inference API",
                "dependencyManager": "pip",
                "appTemplate": "ml-apigw-pytorch",
                "packageType": "Image",
            },
        ]
        with self.assertRaises(UserException):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                pt_explicit=self.pt_explicit,
                package_type="Image",
                base_image="amazon/python3.8-base",
                dependency_manager="pip",
                app_template=None,
                name=self.name,
                output_dir=self.output_dir,
                location=None,
                runtime=None,
                no_input=self.no_input,
                extra_context=self.extra_context,
            )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    def test_init_cli_image_pool_with_base_image_having_multiple_managed_template_and_provided_app_template_not_matching_any_managed_templates(
        self,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "python3.8-image/cookiecutter-aws-sam-hello-python-lambda-image",
                "displayName": "Hello World Lambda Image Example",
                "dependencyManager": "pip",
                "appTemplate": "hello-world-lambda-image",
                "packageType": "Image",
            },
            {
                "directory": "python3.8-image/cookiecutter-ml-apigw-pytorch",
                "displayName": "PyTorch Machine Learning Inference API",
                "dependencyManager": "pip",
                "appTemplate": "ml-apigw-pytorch",
                "packageType": "Image",
            },
        ]
        with self.assertRaises(UserException):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                pt_explicit=self.pt_explicit,
                package_type="Image",
                base_image="amazon/python3.8-base",
                dependency_manager="pip",
                app_template="Not-ml-apigw-pytorch",  # different value than appTemplates shown in the manifest above
                name=self.name,
                output_dir=self.output_dir,
                location=None,
                runtime=None,
                no_input=self.no_input,
                extra_context=self.extra_context,
            )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_image_pool_with_base_image_having_multiple_managed_template_with_matching_app_template_provided(
        self,
        generate_project_patch,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "python3.8-image/cookiecutter-aws-sam-hello-python-lambda-image",
                "displayName": "Hello World Lambda Image Example",
                "dependencyManager": "pip",
                "appTemplate": "hello-world-lambda-image",
                "packageType": "Image",
            },
            {
                "directory": "python3.8-image/cookiecutter-ml-apigw-pytorch",
                "displayName": "PyTorch Machine Learning Inference API",
                "dependencyManager": "pip",
                "appTemplate": "ml-apigw-pytorch",
                "packageType": "Image",
            },
        ]
        init_cli(
            ctx=self.ctx,
            no_interactive=True,
            pt_explicit=True,
            package_type="Image",
            base_image="amazon/python3.8-base",
            dependency_manager="pip",
            app_template="ml-apigw-pytorch",  # same value as one appTemplate in the manifest above
            name=self.name,
            output_dir=None,
            location=None,
            runtime=None,
            no_input=None,
            extra_context=None,
        )
        generate_project_patch.assert_called_once_with(
            os.path.normpath("repository/python3.8-image/cookiecutter-ml-apigw-pytorch"),  # location
            "Image",  # package_type
            "python3.8",  # runtime
            "pip",  # dependency_manager
            self.output_dir,
            self.name,
            True,  # no_input
            ANY,
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_image_pool_with_base_image_having_one_managed_template_does_not_need_app_template_argument(
        self,
        generate_project_patch,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "python3.8-image/cookiecutter-ml-apigw-pytorch",
                "displayName": "PyTorch Machine Learning Inference API",
                "dependencyManager": "pip",
                "appTemplate": "ml-apigw-pytorch",
                "packageType": "Image",
            },
        ]
        init_cli(
            ctx=self.ctx,
            no_interactive=True,
            pt_explicit=True,
            package_type="Image",
            base_image="amazon/python3.8-base",
            dependency_manager="pip",
            app_template=None,
            name=self.name,
            output_dir=None,
            location=None,
            runtime=None,
            no_input=None,
            extra_context=None,
        )
        generate_project_patch.assert_called_once_with(
            os.path.normpath("repository/python3.8-image/cookiecutter-ml-apigw-pytorch"),  # location
            "Image",  # package_type
            "python3.8",  # runtime
            "pip",  # dependency_manager
            self.output_dir,
            self.name,
            True,  # no_input
            ANY,
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_image_pool_with_base_image_having_one_managed_template_with_provided_app_template_matching_the_managed_template(
        self,
        generate_project_patch,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "python3.8-image/cookiecutter-ml-apigw-pytorch",
                "displayName": "PyTorch Machine Learning Inference API",
                "dependencyManager": "pip",
                "appTemplate": "ml-apigw-pytorch",
                "packageType": "Image",
            },
        ]
        init_cli(
            ctx=self.ctx,
            no_interactive=True,
            pt_explicit=True,
            package_type="Image",
            base_image="amazon/python3.8-base",
            dependency_manager="pip",
            app_template="ml-apigw-pytorch",  # same value as appTemplate indicated in the manifest above
            name=self.name,
            output_dir=None,
            location=None,
            runtime=None,
            no_input=None,
            extra_context=None,
        )
        generate_project_patch.assert_called_once_with(
            os.path.normpath("repository/python3.8-image/cookiecutter-ml-apigw-pytorch"),  # location
            "Image",  # package_type
            "python3.8",  # runtime
            "pip",  # dependency_manager
            self.output_dir,
            self.name,
            True,  # no_input
            ANY,
        )

    @patch.object(InitTemplates, "__init__", MockInitTemplates.__init__)
    @patch("samcli.commands.init.init_templates.InitTemplates._init_options_from_manifest")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_image_pool_with_base_image_having_one_managed_template_with_provided_app_template_not_matching_the_managed_template(
        self,
        generate_project_patch,
        init_options_from_manifest_mock,
    ):
        init_options_from_manifest_mock.return_value = [
            {
                "directory": "python3.8-image/cookiecutter-ml-apigw-pytorch",
                "displayName": "PyTorch Machine Learning Inference API",
                "dependencyManager": "pip",
                "appTemplate": "ml-apigw-pytorch",
                "packageType": "Image",
            },
        ]
        with (self.assertRaises(UserException)):
            init_cli(
                ctx=self.ctx,
                no_interactive=True,
                pt_explicit=True,
                package_type="Image",
                base_image="amazon/python3.8-base",
                dependency_manager="pip",
                app_template="NOT-ml-apigw-pytorch",  # different value than appTemplate shown in the manifest above
                name=self.name,
                output_dir=None,
                location=None,
                runtime=None,
                no_input=None,
                extra_context=None,
            )
