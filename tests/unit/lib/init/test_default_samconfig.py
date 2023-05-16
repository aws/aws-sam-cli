from unittest import TestCase
from unittest.mock import Mock, call

from samcli.lib.init import DefaultSamconfig
from samcli.lib.init.default_samconfig import MORE_INFO_COMMENT, Default, WritingType
from samcli.lib.utils.packagetype import IMAGE, ZIP


class TestDefaultSamconfig(TestCase):
    def test_write_zip_template(self):
        default_config = DefaultSamconfig("path", ZIP, "sam-app")
        defaults = [
            Default(WritingType.Both, key="key1", value="value1", command=["test"]),
            Default(WritingType.ZIP, key="key2", value="value2", command=["test"]),
            Default(WritingType.Image, key="key3", value="value3", command=["test"]),
        ]
        default_config._config.put = Mock()
        default_config._write_defaults(defaults=defaults)
        default_config._config.put.assert_has_calls(
            [
                call(cmd_names=["test"], section="parameters", key="key1", value="value1"),
                call(cmd_names=["test"], section="parameters", key="key2", value="value2"),
            ]
        )

    def test_write_image_template(self):
        default_config = DefaultSamconfig("path", IMAGE, "sam-app")
        defaults = [
            Default(WritingType.Both, key="key1", value="value1", command=["test"]),
            Default(WritingType.ZIP, key="key2", value="value2", command=["test"]),
            Default(WritingType.Image, key="key3", value="value3", command=["test"]),
        ]
        default_config._config.put = Mock()
        default_config._write_defaults(defaults=defaults)
        default_config._config.put.assert_has_calls(
            [
                call(cmd_names=["test"], section="parameters", key="key1", value="value1"),
                call(cmd_names=["test"], section="parameters", key="key3", value="value3"),
            ]
        )

    def test_create_zip(self):
        default_config = DefaultSamconfig("path", ZIP, "sam-app")

        default_config._config = Mock()
        default_config._config.flush = Mock()
        default_config._config._write_defaults = Mock()
        default_config._config.put_comment = Mock()
        default_config._config.put = Mock()

        default_config.create()

        default_config._config.flush.assert_called_once()
        default_config._config.put_comment.assert_called_once_with(MORE_INFO_COMMENT)
        default_config._config.put.assert_has_calls(
            [
                call(cmd_names=["global"], section="parameters", key="stack_name", value="sam-app"),
                call(cmd_names=["build"], section="parameters", key="parallel", value=True),
                call(cmd_names=["validate"], section="parameters", key="lint", value=True),
                call(cmd_names=["deploy"], section="parameters", key="resolve_s3", value=True),
                call(cmd_names=["package"], section="parameters", key="resolve_s3", value=True),
                call(cmd_names=["deploy"], section="parameters", key="capabilities", value="CAPABILITY_IAM"),
                call(cmd_names=["deploy"], section="parameters", key="confirm_changeset", value=True),
                call(cmd_names=["sync"], section="parameters", key="watch", value=True),
                call(cmd_names=["local", "start-api"], section="parameters", key="warm_containers", value="EAGER"),
                call(cmd_names=["local", "start-lambda"], section="parameters", key="warm_containers", value="EAGER"),
            ],
            any_order=True,
        )

    def test_create_image(self):
        default_config = DefaultSamconfig("path", IMAGE, "sam-app")

        default_config._config = Mock()
        default_config._config.flush = Mock()
        default_config._config._write_defaults = Mock()
        default_config._config.put_comment = Mock()
        default_config._config.put = Mock()

        default_config.create()

        default_config._config.flush.assert_called_once()
        default_config._config.put_comment.assert_called_once_with(MORE_INFO_COMMENT)
        default_config._config.put.assert_has_calls(
            [
                call(cmd_names=["global"], section="parameters", key="stack_name", value="sam-app"),
                call(cmd_names=["validate"], section="parameters", key="lint", value=True),
                call(cmd_names=["build"], section="parameters", key="parallel", value=True),
                call(cmd_names=["deploy"], section="parameters", key="resolve_image_repos", value=True),
                call(cmd_names=["deploy"], section="parameters", key="capabilities", value="CAPABILITY_IAM"),
                call(cmd_names=["deploy"], section="parameters", key="confirm_changeset", value=True),
                call(cmd_names=["sync"], section="parameters", key="watch", value=True),
                call(cmd_names=["local", "start-api"], section="parameters", key="warm_containers", value="EAGER"),
                call(cmd_names=["local", "start-lambda"], section="parameters", key="warm_containers", value="EAGER"),
            ],
            any_order=True,
        )
