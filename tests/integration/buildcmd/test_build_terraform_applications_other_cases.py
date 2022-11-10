import os
import logging
import shutil
from pathlib import Path
from unittest import skipIf

from parameterized import parameterized

from tests.integration.buildcmd.test_build_terraform_applications import (
    BuildTerraformApplicationIntegBase,
    BuildTerraformApplicationS3BackendIntegBase,
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
        cmdlist = self.get_command_list(beta_features=True, hook_name="terraform", use_container=True)
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_short_format_no_build_image_hooks(self):
        cmdlist = self.get_command_list(beta_features=True, hook_name="terraform")
        cmdlist += ["-u"]
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_success_no_beta_feature_flags_hooks(self):
        cmdlist = self.get_command_list(beta_features=None, hook_name="terraform")
        stdout, stderr, return_code = self.run_command(cmdlist, input=b"N\n\n")
        terraform_beta_feature_prompted_text = (
            f"Supporting Terraform applications is a beta feature.{os.linesep}"
            f"Please confirm if you would like to proceed using AWS SAM CLI with terraform application.{os.linesep}"
            "You can also enable this beta feature with 'sam build --beta-features'."
        )
        self.assertRegex(stdout.decode("utf-8"), terraform_beta_feature_prompted_text)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")

    def test_exit_success_no_beta_features_flags_supplied_hooks(self):
        cmdlist = self.get_command_list(beta_features=False, hook_name="terraform")
        _, stderr, return_code = self.run_command(cmdlist)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")

    def test_build_terraform_with_no_beta_feature_option_in_samconfig_toml(self):
        samconfig_toml_path = Path(self.working_dir).joinpath("samconfig.toml")
        samconfig_lines = [
            bytes("version = 0.1" + os.linesep, "utf-8"),
            bytes("[default.global.parameters]" + os.linesep, "utf-8"),
            bytes("beta_features = false" + os.linesep, "utf-8"),
        ]
        with open(samconfig_toml_path, "wb") as file:
            file.writelines(samconfig_lines)

        cmdlist = self.get_command_list(hook_name="terraform")
        _, stderr, return_code = self.run_command(cmdlist)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")
        # delete the samconfig file
        try:
            os.remove(samconfig_toml_path)
        except FileNotFoundError:
            pass

    def test_build_terraform_with_no_beta_feature_option_as_environment_variable(self):
        environment_variables = os.environ.copy()
        environment_variables["SAM_CLI_BETA_TERRAFORM_SUPPORT"] = "False"

        build_command_list = self.get_command_list(hook_name="terraform")
        _, stderr, return_code = self.run_command(build_command_list, env=environment_variables)
        self.assertEqual(return_code, 0)
        self.assertRegex(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestInvalidTerraformApplicationThatReferToS3BucketNotCreatedYet(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/invalid_no_local_code_project")

    def test_invoke_function(self):
        function_identifier = "aws_lambda_function.function"
        build_cmd_list = self.get_command_list(
            beta_features=True, hook_name="terraform", function_identifier=function_identifier
        )

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
            "beta_features": True,
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
class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/image_based_lambda_functions_local_backend")
    functions = [
        "aws_lambda_function.function_with_non_image_uri",
        "aws_lambda_function.my_image_function",
        "module.l1_lambda.aws_lambda_function.this",
        "module.l1_lambda.module.l2_lambda.aws_lambda_function.this",
        "my_image_function",
        "my_l1_lambda",
        "my_l2_lambda",
        "module.serverless_tf_image_function.aws_lambda_function.this[0]",
        "serverless_tf_image_function",
    ]

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier):
        build_cmd_list = self.get_command_list(
            beta_features=True, hook_name="terraform", function_identifier=function_identifier
        )
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={
                "statusCode": 200,
                "body": "Hello, My friend!",
                "headers": None,
                "multiValueHeaders": None,
            },
        )


@skipIf(
    (not RUN_BY_CANARY and not CI_OVERRIDE),
    "Skip Terraform test cases unless running in CI",
)
class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndS3Backend(
    BuildTerraformApplicationS3BackendIntegBase
):
    terraform_application = Path("terraform/image_based_lambda_functions_s3_backend")
    functions = [
        "aws_lambda_function.function_with_non_image_uri",
        "aws_lambda_function.my_image_function",
        "module.l1_lambda.aws_lambda_function.this",
        "module.l1_lambda.module.l2_lambda.aws_lambda_function.this",
        "my_image_function",
        "my_l1_lambda",
        "my_l2_lambda",
        "module.serverless_tf_image_function.aws_lambda_function.this[0]",
        "serverless_tf_image_function",
    ]

    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier):
        build_cmd_list = self.get_command_list(
            beta_features=True, hook_name="terraform", function_identifier=function_identifier
        )
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={
                "statusCode": 200,
                "body": "Hello, My friend!",
                "headers": None,
                "multiValueHeaders": None,
            },
        )


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
                r"AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one lambda layer",
            ),
            (
                "conditional_layers_null",
                r"AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one lambda layer",
            ),
            (
                "lambda_function_with_count_and_invalid_sam_metadata",
                r"There is no resource found that match the provided resource name aws_lambda_function.function1",
            ),
            (
                "one_lambda_function_linked_to_two_layers",
                r"AWS SAM CLI could not process a Terraform project that contains Lambda functions that are linked to more than one lambda layer",
            ),
            (
                "lambda_function_referencing_local_var_layer",
                r"AWS SAM CLI could not process a Terraform project that uses local variables to define the Lambda functions layers",
            ),
        ]
    )
    def test_unsupported_cases(self, app, expected_error_message):
        self.terraform_application_path = Path(self.terraform_application_path) / app
        shutil.copytree(Path(self.terraform_application_path), Path(self.working_dir))
        build_cmd_list = self.get_command_list(beta_features=True, hook_name="terraform")
        LOG.info("command list: %s", build_cmd_list)
        _, stderr, return_code = self.run_command(build_cmd_list)
        LOG.info(stderr)
        self.assertEqual(return_code, 1)
        self.assertRegex(stderr.decode("utf-8"), expected_error_message)
