
from unittest import TestCase
from mock import Mock, patch, mock_open
from parameterized import parameterized

from samcli.commands.build.command import do_cli
from samcli.commands.exceptions import UserException
from samcli.lib.build.app_builder import UnsupportedRuntimeException, BuildError, UnsupportedBuilderLibraryVersionError


class TestDoCli(TestCase):

    @patch("samcli.commands.build.command.BuildContext")
    @patch("samcli.commands.build.command.ApplicationBuilder")
    @patch("samcli.commands.build.command.yaml_dump")
    @patch("samcli.commands.build.command.os")
    def test_must_succeed_build(self, os_mock, yaml_dump_mock, ApplicationBuilderMock, BuildContextMock):

        ctx_mock = Mock()
        BuildContextMock.return_value.__enter__ = Mock()
        BuildContextMock.return_value.__enter__.return_value = ctx_mock
        builder_mock = ApplicationBuilderMock.return_value = Mock()
        artifacts = builder_mock.build.return_value = "artifacts"
        modified_template = builder_mock.update_template.return_value = "modified template"
        dumped_yaml = yaml_dump_mock.return_value = "dumped yaml"
        m = mock_open()

        with patch("samcli.commands.build.command.open", m):
            do_cli("template", "base_dir", "build_dir", "clean", "use_container",
                   "manifest_path", "docker_network", "skip_pull", "parameter_overrides")

        ApplicationBuilderMock.assert_called_once_with(ctx_mock.function_provider,
                                                       ctx_mock.build_dir,
                                                       ctx_mock.base_dir,
                                                       manifest_path_override=ctx_mock.manifest_path_override,
                                                       container_manager=ctx_mock.container_manager)
        builder_mock.build.assert_called_once()
        builder_mock.update_template.assert_called_once_with(ctx_mock.template_dict,
                                                             ctx_mock.output_template_path,
                                                             artifacts)

        yaml_dump_mock.assert_called_with(modified_template)
        m.assert_called_with(ctx_mock.output_template_path, 'w')
        m.return_value.write.assert_called_with(dumped_yaml)

    @parameterized.expand([
        (UnsupportedRuntimeException(), ),
        (BuildError(), ),
        (UnsupportedBuilderLibraryVersionError(container_name="name", error_msg="msg"), )
    ])
    @patch("samcli.commands.build.command.BuildContext")
    @patch("samcli.commands.build.command.ApplicationBuilder")
    def test_must_catch_known_exceptions(self, exception, ApplicationBuilderMock, BuildContextMock):

        ctx_mock = Mock()
        BuildContextMock.return_value.__enter__ = Mock()
        BuildContextMock.return_value.__enter__.return_value = ctx_mock
        builder_mock = ApplicationBuilderMock.return_value = Mock()

        builder_mock.build.side_effect = exception

        with self.assertRaises(UserException) as ctx:
            do_cli("template", "base_dir", "build_dir", "clean", "use_container",
                   "manifest_path", "docker_network", "skip_pull", "parameteroverrides")

        self.assertEquals(str(ctx.exception), str(exception))
