from unittest import TestCase
from unittest.mock import patch, MagicMock

import click

from samcli.lib.cli_validation.image_repository_validation import image_repository_validation


def _make_ctx_params_side_effect_func(params):
    def side_effect(key, default=None):
        return params.get(key, default)

    return side_effect


class TestImageRepositoryValidation(TestCase):
    def setUp(self):
        @image_repository_validation
        def foo(*args, **kwargs):
            pass

        self.foobar = foo

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_success_ZIP(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = False

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": False,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        self.foobar(project=project_mock)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_success_IMAGE_image_repository(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id.return_value = "HelloWorldFunction"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock]

        params = {
            "guided": False,
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "image_repositories": False,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        self.foobar(project=project_mock)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_success_IMAGE_image_repositories(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock]

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        self.foobar(project=project_mock)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_failure_IMAGE_image_repositories_and_image_repository(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": False,
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "image_repositories": {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar(project=project_mock)
        self.assertIn("'--image-repositories' and '--image-repository' cannot be provided", ex.exception.message)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_failure_IMAGE_image_repositories_incomplete(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        function2_mock = MagicMock()
        function2_mock.item_id = "HelloWorldFunction2"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock, function2_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar(project=project_mock)
        self.assertIn("Incomplete list of function logical ids specified", ex.exception.message)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_failure_IMAGE_missing_image_repositories(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        function2_mock = MagicMock()
        function2_mock.item_id = "HelloWorldFunction2"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock, function2_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": None,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar(project=project_mock)
        self.assertIn("Missing option '--image-repository' or '--image-repositories'", ex.exception.message)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    def test_image_repository_validation_success_missing_image_repositories_guided(self, mock_click):
        # Guided allows for filling of the image repository values.
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        function2_mock = MagicMock()
        function2_mock.item_id = "HelloWorldFunction2"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock, function2_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": True,
            "image_repository": False,
            "image_repositories": None,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_click.get_current_context.return_value = mock_context

        self.foobar(project=project_mock)
