from unittest import TestCase
from unittest.mock import patch, MagicMock

import click

from samcli.lib.cli_validation.image_repository_validation import image_repository_validation
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestImageRepositoryValidation(TestCase):
    def setUp(self):
        @image_repository_validation
        def foo():
            pass

        self.foobar = foo

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_ZIP(self, mock_artifacts, mock_resource_ids, mock_click):
        mock_artifacts.return_value = [ZIP]
        mock_resource_ids.return_value = ["HelloWorldFunction"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [False, False, False, False, False, MagicMock()]
        mock_click.get_current_context.return_value = mock_context

        self.foobar()

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_IMAGE_image_repository(
        self, mock_artifacts, mock_resource_ids, mock_click
    ):
        mock_artifacts.return_value = [IMAGE]
        mock_resource_ids.return_value = ["HelloWorldFunction"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            False,
            False,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context

        self.foobar()

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_IMAGE_image_repositories(
        self, mock_artifacts, mock_resource_ids, mock_click
    ):
        mock_artifacts.return_value = [IMAGE]
        mock_resource_ids.return_value = ["HelloWorldFunction"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            False,
            {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            False,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context
        self.foobar()

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_failure_IMAGE_image_repositories_and_image_repository(
        self, mock_artifacts, mock_resource_ids, mock_click
    ):
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        mock_resource_ids.return_value = ["HelloWorldFunction"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            False,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar()
        self.assertIn("'--image-repositories' and '--image-repository' cannot be provided", ex.exception.message)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_failure_IMAGE_image_repositories_incomplete(
        self, mock_artifacts, mock_resource_ids, mock_click
    ):
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        mock_resource_ids.return_value = ["HelloWorldFunction", "HelloWorldFunction2"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            False,
            {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            False,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar()
        self.assertIn("Incomplete list of function logical ids specified", ex.exception.message)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_failure_IMAGE_missing_image_repositories(
        self, mock_artifacts, mock_resource_ids, mock_click
    ):
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        mock_resource_ids.return_value = ["HelloWorldFunction", "HelloWorldFunction2"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [False, False, False, None, False, MagicMock()]
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar()
        self.assertIn(
            "Missing option '--image-repository', '--image-repositories', or '--resolve-image-repos'",
            ex.exception.message,
        )

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_function_resource_ids")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_missing_image_repositories_guided(
        self, mock_artifacts, mock_resource_ids, mock_click
    ):
        # Guided allows for filling of the image repository values.
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        mock_resource_ids.return_value = ["HelloWorldFunction", "HelloWorldFunction2"]
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [True, True, False, None, False, MagicMock()]
        mock_click.get_current_context.return_value = mock_context
        self.foobar()
