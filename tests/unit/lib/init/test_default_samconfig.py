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
        default_config._write.assert_called_once_with(
            defaults=[Default(writing_type=WritingType.Both, key="stack_name", value=f"sam-app-sam-app")],
            command=["global"],
        )

    def test_write_build(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_build()
        default_config._write.assert_called_once_with(
            defaults=[
                Default(writing_type=WritingType.ZIP, key="cached", value=True),
                Default(writing_type=WritingType.Both, key="parallel", value=True),
            ],
            command=["build"],
        )

    def test_write_deploy(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_deploy()

        default_config._write.assert_called_once_with(
            defaults=[
                Default(writing_type=WritingType.Both, key="capabilities", value="CAPABILITY_IAM"),
                Default(writing_type=WritingType.Both, key="confirm_changeset", value=True),
                Default(writing_type=WritingType.ZIP, key="resolve_s3", value=True),
                Default(writing_type=WritingType.Image, key="resolve_image_repos", value=True),
            ],
            command=["deploy"],
        )

    def test_write_sync(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_sync()
        default_config._write.assert_called_once_with(
            defaults=[Default(writing_type=WritingType.Both, key="watch", value=True)], command=["sync"]
        )

    def test_write_local_start_api(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_local_start_api()
        default_config._write.assert_called_once_with(
            defaults=[Default(writing_type=WritingType.Both, key="warm_containers", value="EAGER")],
            command=["local", "start-api"],
        )

    def test_write_local_start_lambda(self):
        default_config = DefaultSamconfig("path", "ZIP", "sam-app")
        default_config._write = Mock()
        default_config._create_default = Mock()
        default_config._create_default.return_value = "default"
        default_config._write_local_start_lambda()
        default_config._write.assert_called_once_with(
            defaults=[Default(writing_type=WritingType.Both, key="warm_containers", value="EAGER")],
            command=["local", "start-lambda"],
        )
