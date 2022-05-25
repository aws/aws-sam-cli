from unittest import TestCase
from unittest.mock import patch, Mock
from parameterized import parameterized, param


class TestCli(TestCase):
    def test_cli_base_command(self, get_event_mock):
        event_data = "data"
        get_event_mock.return_value = event_data

        ctx_mock = Mock()
        ctx_mock.region = self.region_name
        ctx_mock.profile = self.profile

        # Mock the __enter__ method to return a object inside a context manager
        context_mock = Mock()
        InvokeContextMock.return_value.__enter__.return_value = context_mock

        invoke_cli(
            ctx=ctx_mock,
            function_identifier=self.function_id,
            template=self.template,
            event=self.eventfile,
            no_event=self.no_event,
            env_vars=self.env_vars,
            debug_port=self.debug_ports,
            debug_args=self.debug_args,
            debugger_path=self.debugger_path,
            container_env_vars=self.container_env_vars,
            docker_volume_basedir=self.docker_volume_basedir,
            docker_network=self.docker_network,
            log_file=self.log_file,
            skip_pull_image=self.skip_pull_image,
            parameter_overrides=self.parameter_overrides,
            layer_cache_basedir=self.layer_cache_basedir,
            force_image_build=self.force_image_build,
            shutdown=self.shutdown,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_image=self.invoke_image,
        )

        InvokeContextMock.assert_called_with(
            template_file=self.template,
            function_identifier=self.function_id,
            env_vars_file=self.env_vars,
            docker_volume_basedir=self.docker_volume_basedir,
            docker_network=self.docker_network,
            log_file=self.log_file,
            skip_pull_image=self.skip_pull_image,
            debug_ports=self.debug_ports,
            debug_args=self.debug_args,
            debugger_path=self.debugger_path,
            container_env_vars_file=self.container_env_vars,
            parameter_overrides=self.parameter_overrides,
            layer_cache_basedir=self.layer_cache_basedir,
            force_image_build=self.force_image_build,
            shutdown=self.shutdown,
            aws_region=self.region_name,
            aws_profile=self.profile,
            container_host=self.container_host,
            container_host_interface=self.container_host_interface,
            invoke_images={None: "amazon/aws-sam-cli-emulation-image-python3.6"},
        )
