"""
Test the common CLI options
"""

import os
from datetime import datetime

from unittest import TestCase
from unittest.mock import patch, MagicMock

import click
import pytest
from tomlkit import parse

from samcli.commands._utils.options import (
    get_or_default_template_file_name,
    _TEMPLATE_OPTION_DEFAULT_VALUE,
    guided_deploy_stack_name,
    artifact_callback,
    parameterized_option,
    resolve_s3_callback,
    image_repositories_callback,
    _space_separated_list_func_type,
)
from samcli.commands.package.exceptions import PackageResolveS3AndS3SetError, PackageResolveS3AndS3NotSetError
from samcli.lib.utils.packagetype import IMAGE, ZIP
from tests.unit.cli.test_cli_config_file import MockContext


class Mock:
    pass


class TestGetOrDefaultTemplateFileName(TestCase):
    def test_must_return_abspath_of_user_provided_value(self):
        filename = "foo.txt"
        expected = os.path.abspath(filename)

        result = get_or_default_template_file_name(None, None, filename, include_build=False)
        self.assertEqual(result, expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_yml_extension(self, os_mock):
        expected = "template.yml"

        os_mock.path.exists.return_value = False  # Fake .yaml file to not exist.
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=False)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_yaml_extension(self, os_mock):
        expected = "template.yaml"

        os_mock.path.exists.side_effect = lambda file_name: file_name == expected
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=False)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_json_extension(self, os_mock):
        expected = "template.json"

        os_mock.path.exists.side_effect = lambda file_name: file_name == expected
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=False)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    def test_must_return_built_template(self, os_mock):
        expected = os.path.join(".aws-sam", "build", "template.yaml")

        os_mock.path.exists.return_value = True
        os_mock.path.join = os.path.join  # Use the real method
        os_mock.path.abspath.return_value = "absPath"

        result = get_or_default_template_file_name(None, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, "absPath")
        os_mock.path.abspath.assert_called_with(expected)

    @patch("samcli.commands._utils.options.os")
    @patch("samcli.commands._utils.options.get_template_data")
    def test_verify_ctx(self, get_template_data_mock, os_mock):

        ctx = Mock()
        ctx.default_map = {}

        expected = os.path.join(".aws-sam", "build", "template.yaml")

        os_mock.path.exists.return_value = True
        os_mock.path.join = os.path.join  # Use the real method
        os_mock.path.abspath.return_value = "a/b/c/absPath"
        os_mock.path.dirname.return_value = "a/b/c"
        get_template_data_mock.return_value = "dummy_template_dict"

        result = get_or_default_template_file_name(ctx, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, "a/b/c/absPath")
        self.assertEqual(ctx.samconfig_dir, "a/b/c")
        self.assertEqual(ctx.template_dict, "dummy_template_dict")
        os_mock.path.abspath.assert_called_with(expected)

    def test_verify_ctx_template_file_param(self):

        ctx_mock = Mock()
        ctx_mock.default_map = {"template": "bar.txt"}
        expected_result_from_ctx = os.path.abspath("bar.txt")

        result = get_or_default_template_file_name(ctx_mock, None, _TEMPLATE_OPTION_DEFAULT_VALUE, include_build=True)
        self.assertEqual(result, expected_result_from_ctx)


class TestImageRepositoriesCallBack(TestCase):
    def test_image_repositories_callback(self):
        mock_params = MagicMock()
        result = image_repositories_callback(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=({"a": "b"}, {"c": "d"}),
        )
        self.assertEqual(result, {"a": "b", "c": "d"})

    def test_image_repositories_callback_None(self):
        mock_params = MagicMock()
        self.assertEqual(
            image_repositories_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params), param=MagicMock(), provided_value=()
            ),
            None,
        )


class TestArtifactBasedOptionRequired(TestCase):
    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_required(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = MagicMock()
        mock_params.get = MagicMock()
        s3_bucket = "mock-bucket"
        result = artifact_callback(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=s3_bucket,
            artifact=ZIP,
        )
        self.assertEqual(result, s3_bucket)

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_not_required_resolve_s3_option_present(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = MagicMock()
        mock_params.get = MagicMock(
            side_effect=[
                MagicMock(),  # mock_params.get("t")
                MagicMock(),  # mock_params.get("template-file")
                MagicMock(),  # mock_params.get("template")
                True,  # mock_params.get("resolve_s3")
            ]
        )
        s3_bucket = "mock-bucket"
        result = artifact_callback(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(name="s3_bucket"),
            provided_value=s3_bucket,
            artifact=ZIP,
        )
        # No Exceptions thrown since resolve_s3 is True
        self.assertEqual(result, s3_bucket)

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_not_required_resolve_s3_option_present_in_config_file(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = MagicMock()
        mock_params.get = MagicMock(
            side_effect=[
                MagicMock(),  # mock_params.get("t")
                MagicMock(),  # mock_params.get("template-file")
                MagicMock(),  # mock_params.get("template")
                False,  # mock_params.get("resolve_s3")
            ]
        )
        s3_bucket = "mock-bucket"
        mock_default_map = {"resolve_s3": True}
        result = artifact_callback(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(name="s3_bucket"),
            provided_value=s3_bucket,
            artifact=ZIP,
        )
        # No Exceptions thrown since resolve_s3 is True in config file.
        self.assertEqual(result, s3_bucket)

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_bucket_not_given_error(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = MagicMock()
        mock_params.get.side_effect = [
            MagicMock(),
            False,
        ]
        mock_default_map = MagicMock()
        mock_default_map.get.side_effect = [False]
        mock_param = MagicMock(name="s3_bucket")
        mock_param.name = "s3_bucket"
        s3_bucket = None
        with self.assertRaises(click.BadOptionUsage):
            artifact_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=mock_param,
                provided_value=s3_bucket,
                artifact=ZIP,
            )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_image_based_artifact_image_repo(self, template_artifacts_mock):
        template_artifacts_mock.return_value = [IMAGE]
        mock_params = MagicMock()
        mock_params.get = MagicMock()
        image_repository = "123456789.dkr.ecr.us-east-1.amazonaws.com/sam-cli"

        result = artifact_callback(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=image_repository,
            artifact=IMAGE,
        )
        self.assertEqual(result, image_repository)

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_artifact_different_from_required_option(self, template_artifacts_mock):
        template_artifacts_mock.return_value = [IMAGE, ZIP]
        mock_params = MagicMock()
        mock_params.get = MagicMock(
            side_effect=[
                MagicMock(),  # mock_params.get("t")
                False,  # mock_params.get("resolve_s3")
            ]
        )
        mock_default_map = MagicMock()
        mock_default_map.get = MagicMock(return_value=False)
        param = MagicMock()
        param.name = "s3_bucket"
        param.opts.__getitem__.return_value = ["--s3-bucket"]
        image_repository = None

        with self.assertRaises(click.BadOptionUsage) as ex:
            artifact_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=param,
                provided_value=image_repository,
                artifact=ZIP,
            )
        self.assertEqual(ex.exception.option_name, "s3_bucket")
        self.assertEqual(ex.exception.message, "Missing option '['--s3-bucket']'")


class TestResolveS3CallBackOption(TestCase):
    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_bucket_present_resolve_s3_present(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = {"t": MagicMock(), "template_file": MagicMock(), "template": MagicMock(), "s3_bucket": True}
        mock_default_map = {"s3_bucket": False}
        with self.assertRaises(PackageResolveS3AndS3SetError):
            resolve_s3_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=MagicMock(),
                provided_value=True,
                artifact=ZIP,
                exc_set=PackageResolveS3AndS3SetError,
                exc_not_set=PackageResolveS3AndS3NotSetError,
            )

        # Option is set in the configuration file.
        mock_default_map["s3_bucket"] = True
        mock_params["s3_bucket"] = False

        with self.assertRaises(PackageResolveS3AndS3SetError):
            resolve_s3_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=MagicMock(),
                provided_value=True,
                artifact=ZIP,
                exc_set=PackageResolveS3AndS3SetError,
                exc_not_set=PackageResolveS3AndS3NotSetError,
            )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_bucket_not_present_resolve_s3_not_present(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = {"t": MagicMock(), "template_file": MagicMock(), "template": MagicMock(), "s3_bucket": False}
        mock_default_map = {"s3_bucket": False}
        with self.assertRaises(PackageResolveS3AndS3NotSetError):
            resolve_s3_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=MagicMock(),
                provided_value=False,
                artifact=ZIP,
                exc_set=PackageResolveS3AndS3SetError,
                exc_not_set=PackageResolveS3AndS3NotSetError,
            )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_zip_based_artifact_s3_bucket_not_present_resolve_s3_present(self, template_artifacts_mock):
        # implicitly artifacts are zips
        template_artifacts_mock.return_value = [ZIP]
        mock_params = {"t": MagicMock(), "template_file": MagicMock(), "template": MagicMock(), "s3_bucket": False}
        mock_default_map = {"s3_bucket": False}
        self.assertEqual(
            resolve_s3_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=MagicMock(),
                provided_value=True,
                artifact=ZIP,
                exc_set=PackageResolveS3AndS3SetError,
                exc_not_set=PackageResolveS3AndS3NotSetError,
            ),
            True,
        )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_image_based_artifact_resolve_s3_present(self, template_artifacts_mock):
        template_artifacts_mock.return_value = [IMAGE]
        mock_params = {"t": MagicMock(), "template_file": MagicMock(), "template": MagicMock(), "s3_bucket": False}
        mock_default_map = {"s3_bucket": False}
        # No exception thrown if option is provided or not provided as --s3-bucket or --resolve-s3 is not required.
        for provided_option_value in [True, False]:
            self.assertEqual(
                resolve_s3_callback(
                    ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                    param=MagicMock(),
                    provided_value=provided_option_value,
                    artifact=ZIP,
                    exc_set=PackageResolveS3AndS3SetError,
                    exc_not_set=PackageResolveS3AndS3NotSetError,
                ),
                provided_option_value,
            )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_image_and_zip_based_artifact_s3_bucket_not_present_resolve_s3_not_present(self, template_artifacts_mock):
        template_artifacts_mock.return_value = [IMAGE, ZIP]
        mock_params = {"t": MagicMock(), "template_file": MagicMock(), "template": MagicMock(), "s3_bucket": False}
        mock_default_map = {"s3_bucket": False}
        with self.assertRaises(PackageResolveS3AndS3NotSetError):
            resolve_s3_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=MagicMock(),
                provided_value=False,
                artifact=ZIP,
                exc_set=PackageResolveS3AndS3SetError,
                exc_not_set=PackageResolveS3AndS3NotSetError,
            )

    @patch("samcli.commands._utils.options.get_template_artifacts_format")
    def test_image_and_zip_based_artifact_s3_bucket_present_resolve_s3_not_present(self, template_artifacts_mock):
        template_artifacts_mock.return_value = [IMAGE, ZIP]
        mock_params = {"t": MagicMock(), "template_file": MagicMock(), "template": MagicMock(), "s3_bucket": True}
        mock_default_map = {"s3_bucket": False}
        # No exception thrown, there is --s3-bucket option set.
        self.assertEqual(
            resolve_s3_callback(
                ctx=MockContext(info_name="test", parent=None, params=mock_params, default_map=mock_default_map),
                param=MagicMock(),
                provided_value=False,
                artifact=ZIP,
                exc_set=PackageResolveS3AndS3SetError,
                exc_not_set=PackageResolveS3AndS3NotSetError,
            ),
            False,
        )


class TestGuidedDeployStackName(TestCase):
    def test_must_return_provided_value_guided(self):
        stack_name = "provided-stack"
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=True)
        result = guided_deploy_stack_name(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=stack_name,
        )
        self.assertEqual(result, stack_name)

    def test_must_return_default_value_guided(self):
        stack_name = None
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=True)
        result = guided_deploy_stack_name(
            ctx=MockContext(info_name="test", parent=None, params=mock_params),
            param=MagicMock(),
            provided_value=stack_name,
        )
        self.assertEqual(result, "sam-app")

    def test_must_return_provided_value_non_guided(self):
        stack_name = "provided-stack"
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=False)
        result = guided_deploy_stack_name(ctx=MagicMock(), param=MagicMock(), provided_value=stack_name)
        self.assertEqual(result, "provided-stack")

    def test_exception_missing_parameter_no_value_non_guided(self):
        stack_name = None
        mock_params = MagicMock()
        mock_params.get = MagicMock(return_value=False)
        with self.assertRaises(click.BadOptionUsage):
            guided_deploy_stack_name(
                ctx=MockContext(info_name="test", parent=None, params=mock_params),
                param=MagicMock(),
                provided_value=stack_name,
            )


class TestSpaceSeparatedList(TestCase):
    elements = [
        "CAPABILITY_IAM",
        "CAPABILITY_NAMED_IAM",
    ]

    def test_value_as_spaced_string(self):
        result = _space_separated_list_func_type(" ".join(self.elements))
        self.assertTrue(isinstance(result, list))
        self.assertEqual(result, self.elements)

    def test_value_as_list(self):
        result = _space_separated_list_func_type(self.elements)
        self.assertTrue(isinstance(result, list))
        self.assertEqual(result, self.elements)

    def test_value_as_tuple(self):
        result = _space_separated_list_func_type(tuple(self.elements))
        self.assertTrue(isinstance(result, tuple))
        self.assertEqual(result, tuple(self.elements))

    def test_value_as_tomlkit_array(self):
        content = """
        [test]
        capabilities = [
          "CAPABILITY_IAM",
          "CAPABILITY_NAMED_IAM"
        ]
        """
        doc = parse(content)

        result = _space_separated_list_func_type(doc["test"]["capabilities"])
        self.assertTrue(isinstance(result, list))
        self.assertEqual(result, self.elements)


@pytest.mark.parametrize("test_input", [1, 1.4, True, datetime.now(), {"test": False}, None])
class TestSpaceSeparatedListInvalidDataTypes:
    def test_raise_value_error(self, test_input):
        with pytest.raises(ValueError):
            _space_separated_list_func_type(test_input)


class TestParameterizedOption(TestCase):
    @parameterized_option
    def option_dec_with_value(f, value=2):
        def wrapper():
            return f(value)

        return wrapper

    @parameterized_option
    def option_dec_without_value(f, value=2):
        def wrapper():
            return f(value)

        return wrapper

    @option_dec_with_value(5)
    def some_function_with_value(value):
        return value + 2

    @option_dec_without_value
    def some_function_without_value(value):
        return value + 2

    def test_option_dec_with_value(self):
        self.assertEqual(TestParameterizedOption.some_function_with_value(), 7)

    def test_option_dec_without_value(self):
        self.assertEqual(TestParameterizedOption.some_function_without_value(), 4)
