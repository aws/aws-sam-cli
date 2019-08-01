from unittest import TestCase

from mock import patch
from samcli.commands.destroy import do_cli as destroy_cli


class TestDestroyCli(TestCase):
    def setUp(self):
        self.args = ('--force-upload',)
        self.expected_args = self.args + ("--stack-name", "stackName")

    def test_destroy_must_pass_args(self):
        pass

    def test_pass_only_none_null_arguments(self):
        pass

    def test_role_arn_passed(self):
        pass

    def test_retain_resources_prompt(self):
        pass

    def test_verify_stack_exists(self):
        pass

    def test_verify_stack_exists_with_status(self):
        pass

    def test_termination_protection_enabled(self):
        pass

    def test_access_denied_exception_prompt(self):
        pass

    def test_destroy_wait_called(self):
        pass

    def test_destroy_wait_called_error(self):
        pass
