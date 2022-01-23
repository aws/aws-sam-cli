from parameterized import parameterized_class

from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo
from samcli.lib.bootstrap.companion_stack.companion_stack_builder import CompanionStackBuilder
from unittest import TestCase
from unittest.mock import Mock, patch


class TestCheckSumConsistency(TestCase):
    """This test case is used for surfacing breaking changes companion stacks
    that can be caused by str_checksum.
    If the behavior of str_checksum is changed, please verify the side effects
    that can be caused on companion stacks.
    """

    def test_check_sum_consistency(self):
        companion_stack = CompanionStack("Parent-Stack")
        self.assertEqual(companion_stack.stack_name, "Parent-Stack-8ab67daa-CompanionStack")


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

    def test_stack_name_cutoff(self):
        self.parent_stack_name = "A" * 128
        self.companion_stack = CompanionStack(self.parent_stack_name)
        self.assertEqual(self.companion_stack.stack_name, "A" * 104 + "-checksum-CompanionStack")


@parameterized_class(
    ("function_id", "expected_prefix"),
    [
        ("FunctionA", "FunctionA"),
        ("Stack/FunctionA", "StackFunctionA"),
    ],
)
class TestECRRepo(TestCase):
    function_id = "FunctionA"
    expected_prefix = "FunctionA"

    def setUp(self):
        self.check_sum = "qwertyuiop"
        self.parent_stack_name = "Parent-Stack"

        self.check_sum_patch = patch("samcli.lib.bootstrap.companion_stack.data_types.str_checksum")
        self.check_sum_mock = self.check_sum_patch.start()
        self.check_sum_mock.return_value = self.check_sum

        self.companion_stack_mock = Mock()
        self.companion_stack_mock.escaped_parent_stack_name = "parentstackname"
        self.companion_stack_mock.parent_stack_hash = "abcdefghijklmn"
        self.ecr_repo = ECRRepo(companion_stack=self.companion_stack_mock, function_full_path=self.function_id)

    def tearDown(self):
        self.check_sum_patch.stop()

    def test_logical_id(self):
        self.assertEqual(self.ecr_repo.logical_id, f"{self.expected_prefix}qwertyuiRepo")

    def test_physical_id(self):
        self.assertEqual(
            self.ecr_repo.physical_id, f"parentstacknameabcdefgh/{self.expected_prefix.lower()}qwertyuirepo"
        )

    def test_output_logical_id(self):
        self.assertEqual(self.ecr_repo.output_logical_id, f"{self.expected_prefix}qwertyuiOut")

    def test_get_repo_uri(self):
        self.assertEqual(
            self.ecr_repo.get_repo_uri("12345", "us-west-2"),
            f"12345.dkr.ecr.us-west-2.amazonaws.com/parentstacknameabcdefgh/{self.expected_prefix.lower()}qwertyuirepo",
        )
        self.assertEqual(
            self.ecr_repo.get_repo_uri("12345", "cn-north-1"),
            f"12345.dkr.ecr.cn-north-1.amazonaws.com.cn/parentstacknameabcdefgh/{self.expected_prefix.lower()}qwertyuirepo",
        )

    def test_physical_id_cutoff(self):
        self.companion_stack_mock.escaped_parent_stack_name = "s" * 128
        self.companion_stack_mock.parent_stack_hash = "abcdefghijklmn"

        self.function_id = "F" * 64
        self.ecr_repo = ECRRepo(companion_stack=self.companion_stack_mock, function_full_path=self.function_id)

        self.assertEqual(self.ecr_repo.physical_id, "s" * 128 + "abcdefgh/" + "f" * 64 + "qwertyuirepo")

    def test_logical_id_cutoff(self):
        self.function_id = "F" * 64
        self.ecr_repo = ECRRepo(companion_stack=self.companion_stack_mock, function_full_path=self.function_id)
        self.assertEqual(self.ecr_repo.logical_id, "F" * 52 + "qwertyuiRepo")
