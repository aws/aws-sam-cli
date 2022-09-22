import logging
import shutil

from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired
from typing import Optional
from unittest import skipIf

from parameterized import parameterized

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import CI_OVERRIDE, IS_WINDOWS, RUNNING_ON_CI


LOG = logging.getLogger(__name__)


class BuildTerraformApplicationIntegBase(BuildIntegBase):
    terraform_application: Optional[Path] = None
    template = None

    @classmethod
    def setUpClass(cls):
        super(BuildTerraformApplicationIntegBase, cls).setUpClass()
        cls.terraform_application_path = str(Path(cls.test_data_path, cls.terraform_application))

    def run_command(self, command_list, env=None, input=None):
        process = Popen(
            command_list, stdout=PIPE, stderr=PIPE, stdin=PIPE, env=env, cwd=self.terraform_application_path
        )
        try:
            (stdout, stderr) = process.communicate(input=input)
            return stdout, stderr, process.returncode
        except TimeoutExpired:
            process.kill()
            raise


class TestBuildTerraformApplicationsWithInvalidOptions(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/simple_application")

    def test_invalid_coexist_parameters(self):
        self.template_path = "template.yaml"
        cmdlist = self.get_command_list(hook_package_id="terraform")
        _, stderr, return_code = self.run_command(cmdlist)

        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: Parameters hook-package-id, and t,template-file,template,parameter-overrides can "
            "not be used together",
        )
        self.assertNotEqual(return_code, 0)

    def test_invalid_hook_package_id(self):
        cmdlist = self.get_command_list(hook_package_id="tf")
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Invalid value: tf is not a valid hook package id.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_no_build_image_hooks(self):
        cmdlist = self.get_command_list(beta_features=True, hook_package_id="terraform", use_container=True)
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_failed_use_container_short_format_no_build_image_hooks(self):
        cmdlist = self.get_command_list(beta_features=True, hook_package_id="terraform")
        cmdlist += ["-u"]
        _, stderr, return_code = self.run_command(cmdlist)
        process_stderr = stderr.strip()
        self.assertRegex(
            process_stderr.decode("utf-8"),
            "Error: Missing required parameter --build-image.",
        )
        self.assertNotEqual(return_code, 0)

    def test_exit_success_no_beta_feature_flags_hooks(self):
        cmdlist = self.get_command_list(beta_features=None, hook_package_id="terraform")
        _, stderr, return_code = self.run_command(cmdlist, input=b"N\n\n")
        self.assertEqual(return_code, 0)
        self.assertEqual(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")

    def test_exit_success_no_beta_features_flags_supplied_hooks(self):
        cmdlist = self.get_command_list(beta_features=False, hook_package_id="terraform")
        _, stderr, return_code = self.run_command(cmdlist)
        self.assertEqual(return_code, 0)
        self.assertEqual(stderr.strip().decode("utf-8"), "Terraform Support beta feature is not enabled.")


class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    terraform_application = Path("terraform/zip_based_lambda_functions_local_backend")
    functions = [
        "aws_lambda_function.from_localfile",
        "aws_lambda_function.from_s3",
        "module.level1_lambda.aws_lambda_function.this",
        "module.level1_lambda.module.level2_lambda.aws_lambda_function.this",
        "my_function_from_localfile",
        "my_function_from_s3",
        "my_level1_lambda",
        "my_level2_lambda",
    ]
    
    def tearDown(self):
        try:
            shutil.rmtree(str(Path(self.terraform_application_path) / ".aws-sam"))
            shutil.rmtree(str(Path(self.terraform_application_path) / ".aws-sam-iacs"))
            shutil.rmtree(str(Path(self.terraform_application_path) / ".terraform"))
        except FileNotFoundError:
            pass
        
        try:
            (Path(self.terraform_application_path) / "terraform.tfstate").unlink()
        except FileNotFoundError:
            pass
        
        try:
            (Path(self.terraform_application_path) / "terraform.tfstate.backup").unlink()
        except FileNotFoundError:
            pass
        
        try:
            (Path(self.terraform_application_path) / ".terraform.lock.hcl").unlink()
        except FileNotFoundError:
            pass
        
        super().tearDown()
    
    @skipIf(
        not CI_OVERRIDE,
        "Skip Terraform test cases unless running in CI",
    )
    @parameterized.expand(functions)
    def test_build_and_invoke_lambda_functions(self, function_identifier):
        build_cmd_list = self.get_command_list(
            beta_features=True,
            hook_package_id="terraform",
            function_identifier=function_identifier
        )
        LOG.info("command list: %s", build_cmd_list)
        _, _, return_code = self.run_command(build_cmd_list)
        self.assertEqual(return_code, 0)

        self._verify_invoke_built_function(
            template_path=str(Path(self.terraform_application_path) / ".aws-sam/build/template.yaml"),
            function_logical_id=function_identifier,
            overrides=None,
            expected_result={"statusCode": 200, "body": "[]"}
        )


class TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndS3Backend(BuildTerraformApplicationIntegBase):
    pass


class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndLocalBackend(BuildTerraformApplicationIntegBase):
    pass


class TestBuildTerraformApplicationsWithImageBasedLambdaFunctionAndS3Backend(BuildTerraformApplicationIntegBase):
    pass