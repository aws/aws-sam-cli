from samcli.lib.bootstrap.companion_stack.companion_stack_manager_helper import CompanionStackManagerHelper
from unittest import TestCase
from unittest.mock import Mock, patch


class TestCompanionStackManagerHelper(TestCase):
    def setUp(self):
        self.stack_name = "stackname"
        self.function_a_id = "FunctionA"
        self.function_b_id = "FunctionB"
        self.function_c_id = "FunctionC"
        self.get_template_function_resource_ids_patch = patch(
            "samcli.lib.bootstrap.companion_stack.companion_stack_manager_helper.get_template_function_resource_ids"
        )
        self.get_template_function_resource_ids_mock = self.get_template_function_resource_ids_patch.start()
        self.get_template_function_resource_ids_mock.return_value = [self.function_a_id, self.function_b_id]

        self.companion_stack_manager_patch = patch(
            "samcli.lib.bootstrap.companion_stack.companion_stack_manager_helper.CompanionStackManager"
        )
        self.companion_stack_manager_mock = self.companion_stack_manager_patch.start().return_value
        self.companion_stack_manager_mock.list_deployed_repos.return_value = []
        self.companion_stack_manager_mock.get_repo_uri.return_value = ""
        self.companion_stack_manager_mock.is_repo_uri.return_value = True
        self.companion_stack_manager_mock.get_unreferenced_repos.return_value = [Mock()]

        self.manager_helper = CompanionStackManagerHelper(
            self.stack_name, "region", "s3_bucket", "s3_prefix", "template_file", {}
        )

    def tearDown(self):
        self.get_template_function_resource_ids_patch.stop()
        self.companion_stack_manager_patch.stop()

    def test_init(self):
        self.assertEqual(self.manager_helper.missing_repo_functions, [self.function_a_id, self.function_b_id])
        self.assertEqual(len(self.manager_helper.unreferenced_repos), 1)

    def test_update_specified_image_repos(self):
        self.manager_helper.update_specified_image_repos({"FunctionA": "abc"})
        self.assertEqual(self.manager_helper.missing_repo_functions, [self.function_b_id])
        self.assertEqual(len(self.manager_helper.unreferenced_repos), 1)

    def test_remove_unreferenced_repos_from_mapping(self):
        self.companion_stack_manager_mock.get_repo_uri = lambda x: "repo_uri"

        image_repositories = {self.function_a_id: "a", self.function_b_id: "b", self.function_c_id: "repo_uri"}
        init_image_repositories = image_repositories.copy()
        output_image_repositories = self.manager_helper.remove_unreferenced_repos_from_mapping(image_repositories)
        self.assertEqual(init_image_repositories, image_repositories)
        self.assertEqual(output_image_repositories, {self.function_a_id: "a", self.function_b_id: "b"})
