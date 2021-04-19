from samcli.lib.bootstrap.companion_stack.companion_stack_builder import CompanionStackBuilder
from unittest import TestCase
from unittest.mock import Mock, patch


class TestCompanionStackBuilder(TestCase):
    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_builder.ECRRepo")
    def test_building_single_function(self, ecr_repo_mock):
        companion_stack_name = "CompanionStackA"
        function_a = "FunctionA"

        repo_logical_id = "RepoLogicalIDA"
        repo_physical_id = "RepoPhysicalIDA"
        repo_output_id = "RepoOutputIDA"

        ecr_repo_instance = ecr_repo_mock.return_value
        ecr_repo_instance.logical_id = repo_logical_id
        ecr_repo_instance.physical_id = repo_physical_id
        ecr_repo_instance.output_logical_id = repo_output_id

        companion_stack = Mock()
        companion_stack.stack_name = companion_stack_name
        builder = CompanionStackBuilder(companion_stack)

        builder.add_function(function_a)
        template = builder.build()
        self.assertIn(f'"{repo_logical_id}":', template)
        self.assertIn(f'"RepositoryName": "{repo_physical_id}"', template)
        self.assertIn(f'"{repo_output_id}":', template)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_builder.ECRRepo")
    def test_building_multiple_functions(self, ecr_repo_mock):
        companion_stack_name = "CompanionStackA"
        function_prefix = "Function"
        function_names = ["A", "B", "C", "D", "E", "F"]

        repo_logical_id_prefix = "RepoLogicalID"
        repo_physical_id_prefix = "RepoPhysicalID"
        repo_output_id_prefix = "RepoOutputID"

        ecr_repo_instances = list()
        for function_name in function_names:
            ecr_repo_instance = Mock()
            ecr_repo_instance.logical_id = repo_logical_id_prefix + function_name
            ecr_repo_instance.physical_id = repo_physical_id_prefix + function_name
            ecr_repo_instance.output_logical_id = repo_output_id_prefix + function_name
            ecr_repo_instances.append(ecr_repo_instance)

        ecr_repo_mock.side_effect = ecr_repo_instances

        companion_stack = Mock()
        companion_stack.stack_name = companion_stack_name
        builder = CompanionStackBuilder(companion_stack)

        for function_name in function_names:
            builder.add_function(function_prefix + function_name)
        template = builder.build()
        for function_name in function_names:
            self.assertIn(f'"{repo_logical_id_prefix + function_name}":', template)
            self.assertIn(f'"RepositoryName": "{repo_physical_id_prefix + function_name}"', template)
            self.assertIn(f'"{repo_output_id_prefix + function_name}":', template)

    @patch("samcli.lib.bootstrap.companion_stack.companion_stack_builder.ECRRepo")
    def test_mapping_multiple_functions(self, ecr_repo_mock):
        companion_stack_name = "CompanionStackA"
        function_prefix = "Function"
        function_names = ["A", "B", "C", "D", "E", "F"]

        repo_logical_id_prefix = "RepoLogicalID"
        repo_physical_id_prefix = "RepoPhysicalID"
        repo_output_id_prefix = "RepoOutputID"

        ecr_repo_instances = list()
        for function_name in function_names:
            ecr_repo_instance = Mock()
            ecr_repo_instance.logical_id = repo_logical_id_prefix + function_name
            ecr_repo_instance.physical_id = repo_physical_id_prefix + function_name
            ecr_repo_instance.output_logical_id = repo_output_id_prefix + function_name
            ecr_repo_instances.append(ecr_repo_instance)

        ecr_repo_mock.side_effect = ecr_repo_instances

        companion_stack = Mock()
        companion_stack.stack_name = companion_stack_name
        builder = CompanionStackBuilder(companion_stack)

        for function_name in function_names:
            builder.add_function(function_prefix + function_name)
        for function_name in function_names:
            self.assertIn(
                (function_prefix + function_name, ecr_repo_instances[function_names.index(function_name)]),
                builder.repo_mapping.items(),
            )
