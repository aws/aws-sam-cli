import click

from unittest import TestCase
from unittest.mock import Mock, patch, call
from samcli.commands.build.click_container import ContainerOptions


@patch("samcli.commands.build.click_container.ContainerOptions")
class TestContainerOptionsSucceeds(TestCase):
    ctx_mock = Mock()
    opts = {"container_env_var": ["hi=in"], "use_container": True, "resource_logical_id": None}
    ContainerOptionsMock = Mock()
    ContainerOptionsMock.handle_parse_result.return_value = "value"

    def test_container_options(self, ContainerOptionsMock):
        self.assertEqual(self.ContainerOptionsMock.handle_parse_result(self.ctx_mock, self.opts, []), "value")


class TestContainerOptionsFails(TestCase):
    ctx_mock = Mock()
    opts = {"container_env_var": ["hi=in"], "resource_logical_id": None}
    args = ["--container-env-var"]
    container_opt = ContainerOptions(args)

    def test_container_options_failure(self):
        with self.assertRaises(click.UsageError) as err:
            self.container_opt.handle_parse_result(self.ctx_mock, self.opts, [])
        self.assertEqual(
            str(err.exception),
            "Missing required parameter, need the --use-container flag in order to use --container-env-var flag.",
        )
