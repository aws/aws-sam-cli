import os
import logging
import shutil
from pathlib import Path
from unittest import skipIf

from parameterized import parameterized, parameterized_class

from tests.integration.buildcmd.test_build_terraform_applications import (
    BuildTerraformApplicationIntegBase,
)
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUN_BY_CANARY

LOG = logging.getLogger(__name__)
S3_SLEEP = 3


class TestBuildTerraformApplicationsWithInvalidOptions(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/simple_application")

    def test_invalid_coexist_parameters(self):
        self.template_path = "template.yaml"
        cmdlist = self.get_command_list(hook_name="terraform")
        _, stderr, return_code = self.run_command(cmdlist)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-name, and t,template-file,template,parameter-overrides cannot "
            "be used together",
        )
        self.assertNotEqual(return_code, 0)

    def test_invalid_hook_name(self):
        cmdlist = self.get_command_list(hook_name="tf")
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook name.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_no_build_image_hooks(self):
        cmdlist = self.get_command_list(hook_name="terraform", use_container=True)
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_project_root_dir_no_hooks(self):
        cmdlist = self.get_command_list(project_root_dir="/path")
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing option --hook-name",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_project_root_dir_not_parent_of_current_directory(self):
        cmdlist = self.get_command_list(hook_name="terraform", project_root_dir="/path")
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: /path is not a valid value for Terraform Project Root Path. It should "
            "be a parent of the current directory that contains the root module of the terraform project.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_short_format_no_build_image_hooks(self):
        cmdlist = self.get_command_list(hook_name="terraform")
        cmdlist += ["-u"]
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidTerraformApplicationThatReferToS3BucketNotCreatedYet(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/invalid_no_local_code_project")

    def test_invoke_function(self):
        function_identifier = "aws_lambda_function.function"
        build_cmd_list = self.get_command_list(hook_name="terraform", function_identifier=function_identifier)

        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()

        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Lambda resource aws_lambda_function.function is referring to an S3 bucket that is not created yet, "
            "and there is no sam metadata resource set for it to build its code locally",
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidBuildTerraformApplicationsWithZipBasedLambdaFunctionAndS3BackendNoS3Config(
    BuildTerraformApplicationIntegBase
):
    terraform_application = (
        Path("terraform/zip_based_lambda_functions_s3_backend")
        if not IS_WINDOWS
        else Path("terraform/zip_based_lambda_functions_s3_backend_windows")
    )

    def test_build_no_s3_config(self):
        command_list_parameters = {
            "hook_name": "terraform",
        }
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()
        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        self.assertNotEqual(return_code, 0)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestUnsupportedCases(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/unsupported")

    def setUp(self):
        super().setUp()
        shutil.rmtree(Path(self.working_dir))

    @parameterized.expand(
        [
            (
                "conditional_layers",
                r"AWS SAM CLI could not process a Terraform project that contains a source "
                r"resource that is linked to more than one destination resource",
            ),
            (
                "conditional_layers_null",
                r"AWS SAM CLI could not process a Terraform project that contains a source "
                r"resource that is linked to more than one destination resource",
            ),
            (
                "lambda_function_with_count_and_invalid_sam_metadata",
                r"There is no resource found that match the provided resource name aws_lambda_function.function1",
            ),
            (
                "one_lambda_function_linked_to_two_layers",
                r"AWS SAM CLI could not process a Terraform project that contains a source "
                r"resource that is linked to more than one destination resource",
            ),
            (
                "lambda_function_referencing_local_var_layer",
                r"AWS SAM CLI could not process a Terraform project that uses local "
                r"variables to define linked resources",
            ),
        ]
    )
    def test_unsupported_cases(self, app, expected_error_message):
        apply_disclaimer_message = "Unresolvable attributes discovered in project, run terraform apply to resolve them."

        self.terraform_application_path = Path(self.terraform_application_path) / app
        shutil.copytree(Path(self.terraform_application_path), Path(self.working_dir))
        build_cmd_list = self.get_command_list(hook_name="terraform")
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)

        output = stderr.decode("utf-8")

        self.assertEqual(return_code, 1)
        self.assertRegex(output, expected_error_message)
        self.assertRegex(output, apply_disclaimer_message)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    [
        {"app": "conditional_layers"},
        {"app": "conditional_layers_null"},
        {"app": "one_lambda_function_linked_to_two_layers"},
        {"app": "lambda_function_referencing_local_var_layer"},
    ]
)
class TestUnsupportedCasesAfterApply(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/unsupported")

    def setUp(self):
        super().setUp()
        shutil.rmtree(Path(self.working_dir))
        self.terraform_application_path = Path(self.terraform_application_path) / self.app

        shutil.copytree(Path(self.terraform_application_path), Path(self.working_dir))
        init_command = ["terraform", "init"]
        LOG.info("init tf project command: %s", init_command)
        stdout, stderr, return_code = self.run_command(init_command)
        if return_code != 0:
            LOG.info(stdout)
            LOG.info(stderr)
        self.assertEqual(return_code, 0)
        apply_command = ["terraform", "apply", "-auto-approve"]
        LOG.info("apply tf project command: %s", apply_command)
        stdout, stderr, return_code = self.run_command(apply_command)
        if return_code != 0:
            LOG.info(stdout)
            LOG.info(stderr)
        self.assertEqual(return_code, 0)

    def tearDown(self):
        destroy_command = ["terraform", "destroy", "-auto-approve"]
        LOG.info("destroy tf project command: %s", destroy_command)
        stdout, stderr, return_code = self.run_command(destroy_command)
        if return_code != 0:
            LOG.info(stdout)
            LOG.info(stderr)
        self.assertEqual(return_code, 0)

    def test_unsupported_cases_runs_after_apply(self):
        build_cmd_list = self.get_command_list(hook_name="terraform")
        LOG.info("command list: %s", build_cmd_list)
        _, _, return_code = self.run_command(build_cmd_list)
        self.assertEqual(return_code, 0)
        self._verify_invoke_built_function(
            function_logical_id="aws_lambda_function.function1",
            overrides=None,
            expected_result={"statusCode": 200, "body": "hello world 1"},
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildGoFunctionAndKeepPermissions(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/go_lambda_function_check_keep_permissions")

    def test_invoke_function(self):
        function_identifier = "hello-world-function"
        build_cmd_list = self.get_command_list(hook_name="terraform", function_identifier=function_identifier)

        LOG.info("command list: %s", build_cmd_list)
        environment_variables = os.environ.copy()

        _, stderr, return_code = self.run_command(build_cmd_list, env=environment_variables)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result="{'message': 'Hello World'}",
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
@parameterized_class(
    ("build_in_container",),
    [
        (False,),
        (True,),
    ],
)
class TestBuildTerraformNestedDirectories(BuildTerraformApplicationIntegBase):
    terraform_application = (
        Path("terraform/application_outside_root_directory")
        if not IS_WINDOWS
        else Path("terraform/application_outside_root_directory_windows")
    )

    functions = [
        ("aws_lambda_function.function1", "hello world 1"),
        ("module.function2.aws_lambda_function.this", "hello world 1"),
    ]

    @classmethod
    def setUpClass(cls):
        if IS_WINDOWS and cls.build_in_container:
            # we use this TF project to test sam build in container on windows as we need to run a linux bash script for
            # build, and also we need to remove the Serverless TF functions from this project.
            # that is why we need to use a new project and not one of the existing linux or windows projects
            cls.terraform_application = "terraform/application_outside_root_directory_windows_container"
        if not IS_WINDOWS:
            # The following functions are defined using serverless tf module, and since Serverless TF has some issue
            # while executing `terraform plan` in windows, we removed these function from the TF projects we used in
            # testing on Windows, and only test them on linux.
            # check the Serverless TF issue https://github.com/terraform-aws-modules/terraform-aws-lambda/issues/142
            cls.functions += [
                ("module.function7.aws_lambda_function.this[0]", "hello world 1"),
            ]
        super().setUpClass()

    def setUp(self):
        super().setUp()
        self.project_dir = self.working_dir
        self.working_dir = f"{self.working_dir}/root_module"

    def tearDown(self):
        if self.project_dir:
            self.working_dir = self.project_dir
        super().tearDown()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output):
        command_list_parameters = {
            "hook_name": "terraform",
            "function_identifier": function_identifier,
            "project_root_dir": "./..",
        }
        if self.build_in_container:
            command_list_parameters["use_container"] = True
            command_list_parameters["build_image"] = self.docker_tag
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        stdout, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info("sam build stdout: %s", stdout.decode("utf-8"))
        LOG.info("sam build stderr: %s", stderr.decode("utf-8"))
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsNestedDirectoriesGetParametersFromSamConfig(BuildTerraformApplicationIntegBase):
    terraform_application = (
        Path("terraform/application_outside_root_directory")
        if not IS_WINDOWS
        else Path("terraform/application_outside_root_directory_windows")
    )

    functions = [
        ("aws_lambda_function.function1", "hello world 1"),
    ]

    def setUp(self):
        super().setUp()
        self.project_dir = self.working_dir
        self.working_dir = f"{self.working_dir}/root_module"

    def tearDown(self):
        if self.project_dir:
            self.working_dir = self.project_dir
        super().tearDown()

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier, expected_output):
        command_list_parameters = {
            "config_file": "input_samconfig.yaml",
            "function_identifier": function_identifier,
        }
        build_cmd_list = self.get_command_list(**command_list_parameters)
        LOG.info("command list: %s", build_cmd_list)
        stdout, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info("sam build stdout: %s", stdout.decode("utf-8"))
        LOG.info("sam build stderr: %s", stderr.decode("utf-8"))
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": expected_output},
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsWithBlockedEnvironVariables(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/simple_application")

    @parameterized.expand(
        [
            ("TF_CLI_ARGS", "-destroy"),
            ("TF_CLI_ARGS", "-target=some.module"),
            ("TF_CLI_ARGS_plan", "-destroy"),
            ("TF_CLI_ARGS_plan", "-target=some.module"),
            ("TF_CLI_ARGS_apply", "-destroy"),
            ("TF_CLI_ARGS_apply", "-target=some.module"),
        ]
    )
    def test_blocked_env_variables(self, env_name, env_value):
        cmdlist = self.get_command_list(hook_name="terraform", beta_features=True)

        env_variables = os.environ.copy()
        env_variables[env_name] = env_value

        _, stderr, return_code = self.run_command(cmdlist, env=env_variables)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Environment variable '%s' contains a blocked argument, please validate it does not contain: ['-destroy', '-target']"
            % env_name,
        )
        self.assertNotEqual(return_code, 0)


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestTerraformHandlesExceptionFromBinary(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/broken_tf")

    @parameterized.expand([True, False])
    def test_subprocess_handler(self, debug_flag):
        err_message = (
            "Failed to execute the subprocess. The process ['terraform', 'init', '-input=false'] returned a non-zero "
            "exit code 1."
        )
        terraform_error_message = "Error: Unclosed configuration block"
        stack_trace_error = "unexpected error was encountered while executing 'sam build'"
        cmdlist = self.get_command_list(
            hook_name="terraform",
            debug=debug_flag,
        )
        # add time out, so if the process hangs, the testing will not hang, but the sam command will be timed out.
        # terraform plan command should fail within seconds, as there is an error in syntax, but we will wait for 5 mins
        # in case if terraform init takes time.
        _, stderr, return_code = self.run_command(cmdlist, timeout=300)
        err_string = stderr.decode("utf-8").strip()
        LOG.info("sam build stderr: %s", err_string)
        self.assertEqual(return_code, 1)
        self.assertIn(err_message, err_string)
        self.assertIn(terraform_error_message, err_string)
        self.assertNotIn(stack_trace_error, err_string)
