import os
import pathlib
import re
from subprocess import Popen, PIPE, TimeoutExpired
import tempfile

from unittest import skipIf
from parameterized import parameterized, param

from samcli.lib.utils.hash import dir_checksum
from .package_integ_base import PackageIntegBase
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Package tests require credentials and CI/CD will only add credentials to the env if the PR is from the same repo.
# This is to restrict package tests to run outside of CI/CD, when the branch is not master and tests are not run by Canary.
SKIP_PACKAGE_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY
TIMEOUT = 300


@skipIf(SKIP_PACKAGE_TESTS, "Skip package tests in CI/CD only")
class TestPackageZip(PackageIntegBase):
    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    @parameterized.expand(["aws-serverless-function.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_package_template_flag(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template=template_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()

        self.assertIn("{bucket_name}".format(bucket_name=self.s3_bucket.name), process_stdout.decode("utf-8"))

    @parameterized.expand(
        [
            ("cdk_v1_synthesized_template_Level1_nested_zip_functions.json", 3),
            ("cdk_v1_synthesized_template_Level2_nested_zip_functions.json", 2),
        ]
    )
    def test_package_nested_template(self, template_file, uploading_count):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template=template_path, force_upload=True
        )

        process = Popen(command_list, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip().decode(("utf-8"))
        uploads = re.findall(r"Uploading to.+", process_stderr)
        self.assertEqual(len(uploads), uploading_count)

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
            "aws-include-transform.yaml",
        ]
    )
    def test_package_barebones(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template_file=template_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()

        self.assertIn("{bucket_name}".format(bucket_name=self.s3_bucket.name), process_stdout.decode("utf-8"))

    def test_package_without_required_args(self):
        command_list = self.get_command_list()

        process = Popen(command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        self.assertNotEqual(process.returncode, 0)

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_prefix(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, template_file=template_path, s3_prefix=self.s3_prefix
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()

        self.assertIn("{bucket_name}".format(bucket_name=self.s3_bucket.name), process_stdout.decode("utf-8"))

        self.assertIn("{s3_prefix}".format(s3_prefix=self.s3_prefix), process_stdout.decode("utf-8"))

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_output_template_file(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        with tempfile.NamedTemporaryFile(delete=False) as output_template:

            command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template_file=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
            )

            process = Popen(command_list, stdout=PIPE)
            try:
                stdout, _ = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            process_stdout = stdout.strip()

            self.assertIn(
                bytes(
                    "Successfully packaged artifacts and wrote output template to file {output_template_file}".format(
                        output_template_file=str(output_template.name)
                    ),
                    encoding="utf-8",
                ),
                process_stdout,
            )

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_json(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        with tempfile.NamedTemporaryFile(delete=False) as output_template:

            command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template_file=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                use_json=True,
            )

            process = Popen(command_list, stdout=PIPE)
            try:
                stdout, _ = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            process_stdout = stdout.strip()

            self.assertIn(
                bytes(
                    "Successfully packaged artifacts and wrote output template to file {output_template_file}".format(
                        output_template_file=str(output_template.name)
                    ),
                    encoding="utf-8",
                ),
                process_stdout,
            )

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_force_upload(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            # Upload twice and see the string to have packaged artifacts both times.
            for _ in range(2):

                command_list = self.get_command_list(
                    s3_bucket=self.s3_bucket.name,
                    template_file=template_path,
                    s3_prefix=self.s3_prefix,
                    output_template_file=output_template.name,
                    force_upload=True,
                )

                process = Popen(command_list, stdout=PIPE)
                try:
                    stdout, _ = process.communicate(timeout=TIMEOUT)
                except TimeoutExpired:
                    process.kill()
                    raise
                process_stdout = stdout.strip()

                self.assertIn(
                    bytes(
                        "Successfully packaged artifacts and wrote output template to file {output_template_file}".format(
                            output_template_file=str(output_template.name)
                        ),
                        encoding="utf-8",
                    ),
                    process_stdout,
                )

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_kms_key(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template_file=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                force_upload=True,
                kms_key_id=self.kms_key,
            )

            process = Popen(command_list, stdout=PIPE)
            try:
                stdout, _ = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            process_stdout = stdout.strip()

            self.assertIn(
                bytes(
                    "Successfully packaged artifacts and wrote output template to file {output_template_file}".format(
                        output_template_file=str(output_template.name)
                    ),
                    encoding="utf-8",
                ),
                process_stdout,
            )

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-serverless-httpapi.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_metadata(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            command_list = self.get_command_list(
                s3_bucket=self.s3_bucket.name,
                template_file=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                force_upload=True,
                metadata={"integ": "yes"},
            )

            process = Popen(command_list, stdout=PIPE)
            try:
                stdout, _ = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            process_stdout = stdout.strip()

            self.assertIn(
                bytes(
                    "Successfully packaged artifacts and wrote output template to file {output_template_file}".format(
                        output_template_file=str(output_template.name)
                    ),
                    encoding="utf-8",
                ),
                process_stdout,
            )

    @parameterized.expand(
        [
            "cdk_v1_synthesized_template_zip_functions.json",
            "aws-serverless-function.yaml",
            "aws-serverless-api.yaml",
            "aws-appsync-graphqlschema.yaml",
            "aws-appsync-resolver.yaml",
            "aws-appsync-functionconfiguration.yaml",
            "aws-lambda-function.yaml",
            "aws-apigateway-restapi.yaml",
            "aws-apigatewayv2-httpapi.yaml",
            "aws-elasticbeanstalk-applicationversion.yaml",
            "aws-cloudformation-moduleversion.yaml",
            "aws-cloudformation-resourceversion.yaml",
            "aws-cloudformation-stack.yaml",
            "aws-serverless-application.yaml",
            "aws-lambda-layerversion.yaml",
            "aws-serverless-layerversion.yaml",
            "aws-glue-job.yaml",
            "aws-serverlessrepo-application.yaml",
            "aws-serverless-statemachine.yaml",
            "aws-stepfunctions-statemachine.yaml",
        ]
    )
    def test_package_with_resolve_s3(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            command_list = self.get_command_list(
                template_file=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                force_upload=True,
                resolve_s3=True,
            )

            process = Popen(command_list, stdout=PIPE)
            try:
                stdout, _ = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            process_stdout = stdout.strip()

            self.assertIn(
                bytes(
                    "Successfully packaged artifacts and wrote output template to file {output_template_file}".format(
                        output_template_file=str(output_template.name)
                    ),
                    encoding="utf-8",
                ),
                process_stdout,
            )

    @parameterized.expand([(True,), (False,)])
    def test_package_with_no_progressbar(self, no_progressbar):
        template_path = self.test_data_path.joinpath("aws-serverless-function.yaml")

        with tempfile.NamedTemporaryFile(delete=False) as output_template:
            command_list = self.get_command_list(
                template_file=template_path,
                s3_prefix=self.s3_prefix,
                output_template_file=output_template.name,
                force_upload=True,
                no_progressbar=no_progressbar,
                resolve_s3=True,
            )

            process = Popen(command_list, stdout=PIPE, stderr=PIPE)
            try:
                _, stderr = process.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                process.kill()
                raise
            process_stderr = stderr.strip()

            upload_message = bytes("Uploading to", encoding="utf-8")
            if no_progressbar:
                self.assertNotIn(
                    upload_message,
                    process_stderr,
                )
            else:
                self.assertIn(
                    upload_message,
                    process_stderr,
                )

    @parameterized.expand(
        [
            param("aws-serverless-function-codedeploy-warning.yaml", "CodeDeploy"),
            param("aws-serverless-function-codedeploy-condition-warning.yaml", "CodeDeploy DeploymentGroups"),
        ]
    )
    def test_package_with_warning_template(self, template_file, warning_keyword):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template=template_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip().decode("utf-8")

        # Not comparing with full warning message because of line ending mismatch on
        # windows and non-windows
        self.assertIn(warning_keyword, process_stdout)

    def test_package_with_deep_nested_template(self):
        """
        this template contains two nested stacks:
        - root
          - FunctionA
          - ChildStackX
            - FunctionB
            - ChildStackY
              - FunctionA
              - MyLayerVersion
        """
        template_file = os.path.join("deep-nested", "template.yaml")

        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template=template_path, force_upload=True
        )

        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip().decode("utf-8")

        # there are in total 3 function dir, 1 layer dir and 2 child templates to upload
        uploads = re.findall(r"Uploading to.+", process_stderr)
        self.assertEqual(len(uploads), 6)

        # make sure uploads' checksum match the dirs and child templates
        build_dir = pathlib.Path(os.path.dirname(__file__)).parent.joinpath("testdata", "package", "deep-nested")
        dirs = [
            build_dir.joinpath("FunctionA"),
            build_dir.joinpath("ChildStackX", "FunctionB"),
            build_dir.joinpath("ChildStackX", "ChildStackY", "FunctionA"),
            build_dir.joinpath("ChildStackX", "ChildStackY", "MyLayerVersion"),
        ]
        # here we only verify function/layer code dirs' hash
        # because templates go through some pre-process before being uploaded and the hash can not be determined
        for dir in dirs:
            checksum = dir_checksum(dir.absolute())
            self.assertIn(checksum, process_stderr)

        # verify both child templates are uploaded
        uploads = re.findall(r"\.template", process_stderr)
        self.assertEqual(len(uploads), 2)

    def test_package_with_stackset(self):
        """
        this template contains a stack set:
        - root
          - FunctionA
          - StackSetA
        """
        template_file = os.path.join("stackset", "template.yaml")

        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template=template_path, force_upload=True
        )

        prevdir = os.getcwd()
        os.chdir(os.path.expanduser(os.path.dirname(template_path)))
        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip().decode("utf-8")
        os.chdir(prevdir)

        # there are in total 1 function dir, 1 stackset template to upload
        uploads = re.findall(r"Uploading to.+", process_stderr)
        self.assertEqual(len(uploads), 2)

        # make sure uploads' checksum match the dirs and stackset template
        build_dir = pathlib.Path(os.path.dirname(__file__)).parent.joinpath("testdata", "package", "stackset")
        dirs = [build_dir.joinpath("FunctionA")]
        # here we only verify function/layer code dirs' hash
        # because templates go through some pre-process before being uploaded and the hash can not be determined
        for dir in dirs:
            checksum = dir_checksum(dir.absolute())
            self.assertIn(checksum, process_stderr)

        # verify stack set template is uploaded
        uploads = re.findall(r"\.template", process_stderr)
        self.assertEqual(len(uploads), 1)

    def test_package_with_stackset_in_a_substack(self):
        """
        this template contains a stack set:
        - root
          - ChildStackX
            - FunctionA
            - StackSetA
        """
        template_file = os.path.join("stackset", "nested-template.yaml")

        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template=template_path, force_upload=True
        )

        prevdir = os.getcwd()
        os.chdir(os.path.expanduser(os.path.dirname(template_path)))
        process = Popen(command_list, stdout=PIPE, stderr=PIPE)
        try:
            _, stderr = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stderr = stderr.strip().decode("utf-8")
        os.chdir(prevdir)

        # there are in total 1 child stack, 1 function dir, 1 stackset template to upload
        uploads = re.findall(r"Uploading to.+", process_stderr)
        self.assertEqual(len(uploads), 3)

        # make sure uploads' checksum match the dirs and stackset template
        build_dir = pathlib.Path(os.path.dirname(__file__)).parent.joinpath("testdata", "package", "stackset")
        dirs = [build_dir.joinpath("FunctionA")]
        # here we only verify function/layer code dirs' hash
        # because templates go through some pre-process before being uploaded and the hash can not be determined
        for dir in dirs:
            checksum = dir_checksum(dir.absolute())
            self.assertIn(checksum, process_stderr)

        # verify child stack and stack set templates are uploaded
        uploads = re.findall(r"\.template", process_stderr)
        self.assertEqual(len(uploads), 2)

    @parameterized.expand(["aws-serverless-function-cdk.yaml", "cdk_v1_synthesized_template_zip_functions.json"])
    def test_package_logs_warning_for_cdk_project(self, template_file):
        template_path = self.test_data_path.joinpath(template_file)
        command_list = self.get_command_list(
            s3_bucket=self.s3_bucket.name, s3_prefix=self.s3_prefix, template_file=template_path
        )

        process = Popen(command_list, stdout=PIPE)
        try:
            stdout, _ = process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        process_stdout = stdout.strip()

        warning_message = bytes(
            f"Warning: CDK apps are not officially supported with this command.{os.linesep}"
            "We recommend you use this alternative command: cdk deploy",
            encoding="utf-8",
        )

        self.assertIn(warning_message, stdout)
        self.assertIn("{bucket_name}".format(bucket_name=self.s3_bucket.name), process_stdout.decode("utf-8"))
