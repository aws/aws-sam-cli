import os
from subprocess import Popen, PIPE, TimeoutExpired
from unittest import TestCase

TIMEOUT = 300


class DeployRegressionBase(TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def base_command(self, base):
        command = [base]
        if os.getenv("SAM_CLI_DEV") and base == "sam":
            command = ["samdev"]
        elif base == "aws":
            command = [base, "cloudformation"]

        return command

    def get_deploy_command_list(
        self,
        base="sam",
        s3_bucket=None,
        stack_name=None,
        template=None,
        template_file=None,
        s3_prefix=None,
        capabilities=None,
        force_upload=False,
        notification_arns=None,
        fail_on_empty_changeset=False,
        no_execute_changeset=False,
        parameter_overrides=None,
        role_arn=None,
        kms_key_id=None,
        tags=None,
        profile=None,
        region=None,
        resolve_image_repos=False,
    ):
        command_list = self.base_command(base=base)

        command_list = command_list + ["deploy"]

        if s3_bucket:
            command_list = command_list + ["--s3-bucket", str(s3_bucket)]
        if capabilities:
            command_list = command_list + ["--capabilities", str(capabilities)]
        if parameter_overrides:
            command_list = command_list + ["--parameter-overrides", str(parameter_overrides)]
        if role_arn:
            command_list = command_list + ["--role-arn", str(role_arn)]
        if notification_arns:
            command_list = command_list + ["--notification-arns", str(notification_arns)]
        if stack_name:
            command_list = command_list + ["--stack-name", str(stack_name)]
        if template:
            command_list = command_list + ["--template", str(template)]
        if template_file:
            command_list = command_list + ["--template-file", str(template_file)]
        if s3_prefix:
            command_list = command_list + ["--s3-prefix", str(s3_prefix)]
        if kms_key_id:
            command_list = command_list + ["--kms-key-id", str(kms_key_id)]
        if no_execute_changeset:
            command_list = command_list + ["--no-execute-changeset"]
        if force_upload:
            command_list = command_list + ["--force-upload"]
        if fail_on_empty_changeset:
            command_list = command_list + ["--fail-on-empty-changeset"]
        if tags:
            command_list = command_list + ["--tags", str(tags)]
        if region:
            command_list = command_list + ["--region", str(region)]
        if profile:
            command_list = command_list + ["--profile", str(profile)]
        if resolve_image_repos:
            command_list = command_list + ["--resolve-image-repos"]

        return command_list

    def deploy_regression_check(self, args, sam_return_code=0, aws_return_code=0, commands=[]):
        sam_stack_name = args.get("sam_stack_name", None)
        aws_stack_name = args.get("aws_stack_name", None)
        if sam_stack_name:
            del args["sam_stack_name"]
        if aws_stack_name:
            del args["aws_stack_name"]

        aws_command_list = self.get_deploy_command_list(base="aws", stack_name=aws_stack_name, **args)
        process = Popen(aws_command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        self.assertEqual(process.returncode, aws_return_code)

        sam_command_list = self.get_deploy_command_list(stack_name=sam_stack_name, **args)
        process = Popen(sam_command_list, stdout=PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            process.kill()
            raise
        self.assertEqual(process.returncode, sam_return_code)
