import os
import json
from unittest import TestCase


class SyncIntegBase(TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def base_command(self):
        command = "sam"
        if os.getenv("SAM_CLI_DEV"):
            command = "samdev"

        return command

    def get_sync_command_list(
        self,
        template_file=None,
        code=None,
        watch=None,
        resource_id=None,
        resource=None,
        dependency_layer=None,
        stack_name=None,
        region=None,
        profile=None,
        parameter_overrides=None,
        base_dir=None,
        image_repository=None,
        image_repositories=None,
        s3_prefix=None,
        kms_key_id=None,
        capabilities=None,
        capabilities_list=None,
        role_arn=None,
        notification_arns=None,
        tags=None,
        metadata=None,
    ):
        command_list = [self.base_command(), "sync"]

        command_list += ["-t", str(template_file)]
        if code:
            command_list += ["--code"]
        if watch:
            command_list += ["--watch"]
        if resource_id:
            command_list += ["--resource-id", str(resource_id)]
        if resource:
            command_list += ["--resource", str(resource)]
        if dependency_layer:
            command_list += ["--dependency-layer"]
        if not dependency_layer:
            command_list += ["--no-dependency-layer"]
        if stack_name:
            command_list += ["--stack-name", str(stack_name)]
        if region:
            command_list += ["--region", str(region)]
        if profile:
            command_list += ["--profile", str(profile)]
        if parameter_overrides:
            command_list += ["--parameter-overrides", str(parameter_overrides)]
        if base_dir:
            command_list += ["-s", str(base_dir)]
        if image_repository:
            command_list += ["--image-repository", str(image_repository)]
        if image_repositories:
            command_list += ["--image-repositories", str(image_repositories)]
        if s3_prefix:
            command_list += ["--s3-prefix", str(s3_prefix)]
        if kms_key_id:
            command_list += ["--kms-key-id", str(kms_key_id)]
        if capabilities:
            command_list += ["--capabilities", str(capabilities)]
        elif capabilities_list:
            command_list.append("--capabilities")
            for capability in capabilities_list:
                command_list.append(str(capability))
        if role_arn:
            command_list += ["--role-arn", str(role_arn)]
        if notification_arns:
            command_list += ["--notification-arns", str(notification_arns)]
        if tags:
            command_list += ["--tags", str(tags)]
        if metadata:
            command_list += ["--metadata", json.dumps(metadata)]

        return command_list
