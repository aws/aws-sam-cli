from unittest import TestCase
from unittest.mock import Mock, patch

import click

from samcli.commands.init import non_interactive_validation
from samcli.lib.utils.packagetype import IMAGE, ZIP


class TestNonInteractiveMode(TestCase):
    @patch("samcli.commands.init.click.get_current_context")
    def test_interactive_mode(self, mocked_ctx):
        mocked_ctx.return_value = Mock(
            params={
                "no_interactive": False,
            }
        )

        mocked_func = Mock()
        wrapped_func = non_interactive_validation(mocked_func)
        wrapped_func()

        mocked_func.assert_called_once()

    @patch("samcli.commands.init.click.get_current_context")
    def test_non_interactive_mode_with_non_java_image(self, mocked_ctx):
        mocked_ctx.return_value = Mock(
            params={"no_interactive": True, "package_type": IMAGE, "base_image": "amazon/dotnet5.0"}
        )

        mocked_func = Mock()
        wrapped_func = non_interactive_validation(mocked_func)
        wrapped_func()

        mocked_func.assert_called_once()

    @patch("samcli.commands.init.click.get_current_context")
    def test_non_interactive_mode_with_java_zip_dependency_manager(self, mocked_ctx):
        mocked_ctx.return_value = Mock(
            params={"no_interactive": True, "package_type": ZIP, "dependency_manager": "maven"}
        )
        mocked_func = Mock()
        wrapped_func = non_interactive_validation(mocked_func)

        wrapped_func()
        mocked_func.assert_called_once()

    @patch("samcli.commands.init.click.get_current_context")
    def test_non_interactive_mode_with_java_image_dependency_manager(self, mocked_ctx):
        mocked_ctx.return_value = Mock(
            params={"no_interactive": True, "package_type": IMAGE, "dependency_manager": "maven"}
        )
        mocked_func = Mock()
        wrapped_func = non_interactive_validation(mocked_func)

        wrapped_func()
        mocked_func.assert_called_once()

    @patch("samcli.commands.init.click.get_current_context")
    def test_non_interactive_mode_with_java_image_no_dependency_manager(self, mocked_ctx):
        mocked_ctx.return_value = Mock(
            params={"no_interactive": True, "package_type": IMAGE, "base_image": "amazon/java8"}
        )
        mocked_func = Mock()
        wrapped_func = non_interactive_validation(mocked_func)

        with self.assertRaises(click.UsageError):
            wrapped_func()
        mocked_func.assert_not_called()

    @patch("samcli.commands.init.click.get_current_context")
    def test_non_interactive_mode_with_zip_no_dependency_manager(self, mocked_ctx):
        mocked_ctx.return_value = Mock(params={"no_interactive": True, "package_type": ZIP})
        mocked_func = Mock()
        wrapped_func = non_interactive_validation(mocked_func)

        with self.assertRaises(click.UsageError):
            wrapped_func()
        mocked_func.assert_not_called()
