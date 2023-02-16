from unittest import TestCase
from unittest.mock import Mock, call

from samcli.lib.init import DefaultSamconfig
from samcli.lib.init.default_samconfig import MORE_INFO_COMMENT, Default, WritingType
from samcli.lib.utils.packagetype import IMAGE, ZIP


class TestDefaultSamconfig(TestCase):
    def test_write_zip_template(self):
        default_config = DefaultSamconfig("path", ZIP, "sam-app")
        defaults = [
            Default(WritingType.Both, key="key1", value="value1"),
            Default(WritingType.ZIP, key="key2", value="value2"),
            Default(WritingType.Image, key="key3", value="value3"),
        ]
        default_config._config.put = Mock()
        default_config._write(defaults=defaults, command=["test"])
        default_config._config.put.assert_has_calls(
            [
                call(cmd_names=["test"], section="parameters", key="key1", value="value1"),
                call(cmd_names=["test"], section="parameters", key="key2", value="value2"),
            ]
        )

    def test_write_image_template(self):
        default_config = DefaultSamconfig("path", IMAGE, "sam-app")
        defaults = [
            Default(WritingType.Both, key="key1", value="value1"),
            Default(WritingType.ZIP, key="key2", value="value2"),
            Default(WritingType.Image, key="key3", value="value3"),
        ]
        default_config._config.put = Mock()
        default_config._write(defaults=defaults, command=["test"])
        default_config._config.put.assert_has_calls(
            [
                call(cmd_names=["test"], section="parameters", key="key1", value="value1"),
                call(cmd_names=["test"], section="parameters", key="key3", value="value3"),
            ]
        )

    def test_create(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")

        default_config._config = Mock()
        default_config._config.flush = Mock()
        default_config._config.put_comment = Mock()
        default_config._write_global = Mock()
        default_config._write_build = Mock()
        default_config._write_sync = Mock()
        default_config._write_local_start_api = Mock()
        default_config._write_local_start_lambda = Mock()
        default_config._write_deploy = Mock()

        default_config.create()

        default_config._config.flush.assert_called_once()
        default_config._config.put_comment.assert_called_once_with(MORE_INFO_COMMENT)
        default_config._write_global.assert_called_once()
        default_config._write_build.assert_called_once()
        default_config._write_sync.assert_called_once()
        default_config._write_local_start_api.assert_called_once()
        default_config._write_local_start_lambda.assert_called_once()
        default_config._write_deploy.assert_called_once()

    def test_write_global(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_global()
        default_config._create_default.assert_called_once_with(
            writing_type=WritingType.Both, key="stack_name", value=f"sam-app-sam-app"
        )
        default_config._write.assert_called_once_with(defaults=["default"], command=["global"])

    def test_write_build(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_build()
        default_config._create_default.assert_has_calls(
            [
                call(writing_type=WritingType.ZIP, key="cached", value=True),
                call(writing_type=WritingType.Both, key="parallel", value=True),
            ]
        )
        default_config._write.assert_called_once_with(defaults=["default", "default"], command=["build"])

    def test_write_deploy(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_deploy()
        default_config._create_default.assert_has_calls(
            [
                call(writing_type=WritingType.Both, key="capabilities", value="CAPABILITY_IAM"),
                call(writing_type=WritingType.Both, key="confirm_changeset", value=True),
                call(writing_type=WritingType.ZIP, key="resolve_s3", value=True),
                call(writing_type=WritingType.Image, key="resolve_image_repos", value=True),
            ]
        )
        default_config._write.assert_called_once_with(
            defaults=["default", "default", "default", "default"], command=["deploy"]
        )

    def test_write_sync(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_sync()
        default_config._create_default.assert_called_once_with(writing_type=WritingType.Both, key="watch", value=True)
        default_config._write.assert_called_once_with(defaults=["default"], command=["sync"])

    def test_write_local_start_api(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_local_start_api()
        default_config._create_default.assert_called_once_with(
            writing_type=WritingType.Both, key="warm_containers", value="EAGER"
        )
        default_config._write.assert_called_once_with(defaults=["default"], command=["local", "start-api"])

    def test_write_local_start_lambda(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_local_start_lambda()
        default_config._create_default.assert_called_once_with(
            writing_type=WritingType.Both, key="warm_containers", value="EAGER"
        )
        default_config._write.assert_called_once_with(defaults=["default"], command=["local", "start-lambda"])

    def test_create_default(self):
        expected_default = Default(WritingType.Both, "key", "value")
        self.assertTrue(expected_default, DefaultSamconfig._create_default(WritingType.Both, "key", "value"))
