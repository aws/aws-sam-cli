from textwrap import dedent
from unittest import TestCase
from unittest.mock import patch, Mock

from samcli.lib.cookiecutter import preload_value


class TestPreloadValueFromTomlFile(TestCase):
    toml_text = dedent(
        """\
    version = 0.1
    [default]
    [default.pipeline_bootstrap]
    [default.pipeline_bootstrap.parameters]
    pipeline_user = "pipeline_user_arn"

    [beta]
    [beta.pipeline_bootstrap]
    [beta.pipeline_bootstrap.parameters]
    pipeline_execution_role = "pipeline_execution_role_arn"
    cloudformation_execution_role = "cloudformation_execution_role_arn"
    artifacts_bucket = "artifacts_bucket_name"
    """
    )

    def test_preload_root(self):
        toml_file_path = Mock()
        toml_file_path.read_text.return_value = self.toml_text

        context = preload_value.preload_values_from_toml_file(toml_file_path, {"existing_key": "some_value"})
        self.assertEqual(
            {
                "existing_key": "some_value",
                "$PRELOAD": {
                    "beta": {
                        "pipeline_bootstrap": {
                            "parameters": {
                                "artifacts_bucket": "artifacts_bucket_name",
                                "cloudformation_execution_role": "cloudformation_execution_role_arn",
                                "pipeline_execution_role": "pipeline_execution_role_arn",
                            }
                        }
                    },
                    "default": {"pipeline_bootstrap": {"parameters": {"pipeline_user": "pipeline_user_arn"}}},
                    "version": 0.1,
                },
            },
            context,
        )

    def test_preload_non_exist_toml_file(self):
        toml_file_path = Mock()
        toml_file_path.read_text.side_effect = OSError

        context = preload_value.preload_values_from_toml_file(
            toml_file_path,
            {"existing_key": "some_value"},
        )
        self.assertEqual(
            {
                "existing_key": "some_value",
                "$PRELOAD": {},
            },
            context,
        )


class TestGetPreloadValue(TestCase):
    context = {
        "$PRELOAD": {
            "beta": {
                "pipeline_bootstrap": {
                    "parameters": {
                        "artifacts_bucket": "artifacts_bucket_name",
                        "cloudformation_execution_role": "cloudformation_execution_role_arn",
                        "pipeline_execution_role": "pipeline_execution_role_arn",
                    }
                }
            }
        }
    }

    def test_get_preload_value(self):
        self.assertEqual(
            "cloudformation_execution_role_arn",
            preload_value.get_preload_value(
                self.context, ["beta", "pipeline_bootstrap", "parameters", "cloudformation_execution_role"]
            ),
        )

    def test_get_preload_value_with_invalid_key_path(self):
        self.assertEqual(
            None,
            preload_value.get_preload_value(
                self.context, ["gamma", "pipeline_bootstrap", "parameters", "cloudformation_execution_role"]
            ),
        )

    def test_get_preload_value_with_empty_context(self):
        self.assertEqual(
            None,
            preload_value.get_preload_value(
                {}, ["gamma", "pipeline_bootstrap", "parameters", "cloudformation_execution_role"]
            ),
        )
