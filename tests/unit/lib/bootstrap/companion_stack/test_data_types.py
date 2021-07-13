from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo
from samcli.lib.bootstrap.companion_stack.companion_stack_builder import CompanionStackBuilder
from unittest import TestCase
from unittest.mock import Mock, patch


class TestCompanionStack(TestCase):
    def setUp(self):
        self.check_sum = "checksum"
        self.parent_stack_name = "Parent-Stack"
        self.check_sum_patch = patch("samcli.lib.bootstrap.companion_stack.data_types.str_checksum")
        self.check_sum_mock = self.check_sum_patch.start()
        self.check_sum_mock.return_value = self.check_sum
        self.companion_stack = CompanionStack(self.parent_stack_name)

    def tearDown(self):
        self.check_sum_patch.stop()

    def test_parent_stack_name(self):
        self.assertEqual(self.companion_stack.parent_stack_name, self.parent_stack_name)

    def test_escaped_parent_stack_name(self):
        self.assertEqual(self.companion_stack.escaped_parent_stack_name, "parentstack")

    def test_parent_stack_hash(self):
        self.assertEqual(self.companion_stack.parent_stack_hash, "checksum")

    def test_stack_name(self):
        self.assertEqual(self.companion_stack.stack_name, "Parent-Stack-checksum-CompanionStack")


class TestECRRepo(TestCase):
    def setUp(self):
        self.check_sum = "qwertyuiop"
        self.parent_stack_name = "Parent-Stack"
        self.function_id = "FunctionA"

        self.check_sum_patch = patch("samcli.lib.bootstrap.companion_stack.data_types.str_checksum")
        self.check_sum_mock = self.check_sum_patch.start()
        self.check_sum_mock.return_value = self.check_sum

        self.companion_stack_mock = Mock()
        self.companion_stack_mock.escaped_parent_stack_name = "parentstackname"
        self.companion_stack_mock.parent_stack_hash = "abcdefghijklmn"
        self.ecr_repo = ECRRepo(companion_stack=self.companion_stack_mock, function_logical_id=self.function_id)

    def tearDown(self):
        self.check_sum_patch.stop()

    def test_logical_id(self):
        self.assertEqual(self.ecr_repo.logical_id, "FunctionAqwertyuiRepo")

    def test_physical_id(self):
        self.assertEqual(self.ecr_repo.physical_id, "parentstacknameabcdefgh/functionaqwertyuirepo")

    def test_output_logical_id(self):
        self.assertEqual(self.ecr_repo.output_logical_id, "FunctionAqwertyuiOut")

    def test_get_repo_uri(self):
        self.assertEqual(
            self.ecr_repo.get_repo_uri("12345", "us-west-2"),
            "12345.dkr.ecr.us-west-2.amazonaws.com/parentstacknameabcdefgh/functionaqwertyuirepo",
        )
