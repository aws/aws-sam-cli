from unittest import TestCase

import click
from unittest.mock import patch, MagicMock, Mock

from samcli.commands._utils.exceptions import PackageResolveS3AndS3NotSetError, PackageResolveS3AndS3SetError
from samcli.commands._utils.iac_project_validator import IacProjectValidator


def _make_ctx_params_side_effect_func(params):
    def side_effect(key, default=None):
        return params.get(key, default)

    return side_effect


class TestIacOptionsValidations(TestCase):
    def test_validation_success_cfn_not_require_stack(self):
        params = {"project_type": "CFN"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        project_mock = Mock()
        projector_validator = IacProjectValidator(context_mock, project_mock)
        projector_validator.iac_options_validation(require_stack=False)

    def test_validation_success_cfn_require_stack(self):
        params = {"project_type": "CFN"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        project_mock = Mock()
        projector_validator = IacProjectValidator(context_mock, project_mock)
        projector_validator.iac_options_validation(require_stack=True)

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_validation_fail_cfn_missing_stack_name_when_deploy(self, click_mock):
        params = {"project_type": "CFN"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        context_mock.command_path = "sam deploy"
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        projector_validator = IacProjectValidator(context_mock, project_mock)
        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            projector_validator.iac_options_validation(require_stack=True)
        self.assertEqual(ex.exception.option_name, "--stack-name")
        self.assertEqual(
            ex.exception.message,
            "Missing option '--stack-name', 'sam deploy --guided' can "
            "be used to provide and save needed parameters for future deploys.",
        )

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_validation_fail_cfn_invalid_options(self, click_mock):
        params = {
            "project_type": "CFN",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        projector_validator = IacProjectValidator(context_mock, project_mock)
        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            projector_validator.iac_options_validation(require_stack=True)
        self.assertEqual(ex.exception.option_name, "--cdk-app")
        self.assertEqual(ex.exception.message, "Option '--cdk-app' cannot be used for Project Type 'CFN'")

    def test_validation_success_cdk_not_require_stack(self):
        params = {
            "project_type": "CDK",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]
        projector_validator = IacProjectValidator(context_mock, project_mock)

        projector_validator.iac_options_validation(require_stack=False)

    def test_validation_success_cdk_require_stack(self):
        params = {"project_type": "CDK", "cdk_app": "foo", "stack_name": "stack"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]
        projector_validator = IacProjectValidator(context_mock, project_mock)

        projector_validator.iac_options_validation(require_stack=True)

    def test_validation_success_cdk_no_need_to_specify_stack_name(self):
        params = {
            "project_type": "CDK",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]
        projector_validator = IacProjectValidator(context_mock, project_mock)

        projector_validator.iac_options_validation(require_stack=True)

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_validation_fail_cdk_missing_stack_name(self, click_mock):
        params = {
            "project_type": "CDK",
            "cdk_app": "foo",
        }
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        project_mock.stacks = [Mock(), Mock()]
        projector_validator = IacProjectValidator(context_mock, project_mock)

        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            projector_validator.iac_options_validation(require_stack=True)
        self.assertEqual(ex.exception.option_name, "--stack-name")
        self.assertEqual(ex.exception.message, "More than one stack found. Use '--stack-name' to specify the stack.")

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_validation_fail_cdk_not_found_stack_name(self, click_mock):
        params = {"project_type": "CDK", "cdk_app": "foo", "stack_name": "non_existent_stack"}
        context_mock = MagicMock()
        context_mock.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        click_mock.BadOptionUsage = click.BadOptionUsage

        project_mock = Mock()
        stack_mock = Mock()
        stack_mock.name = "stack"
        project_mock.stacks = [stack_mock]
        project_mock.find_stack_by_name.return_value = None
        projector_validator = IacProjectValidator(context_mock, project_mock)

        with self.assertRaises(click_mock.BadOptionUsage) as ex:
            projector_validator.iac_options_validation(require_stack=True)
        self.assertEqual(ex.exception.option_name, "--stack-name")
        self.assertEqual(ex.exception.message, "Stack with stack name 'non_existent_stack' not found.")


class TestPackageOptionValidation(TestCase):
    def test_guided_success(self):
        project_mock = MagicMock()

        params = {
            "guided": True,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.image_repository_validation()

    def test_asset_ZIP_type_and_resolve_s3_success(self):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True

        params = {
            "guided": False,
            "resolve_s3": True,
            "s3_bucket": False,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_context.default_map.get.return_value = {}

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.package_option_validation()

    def test_asset_ZIP_type_and_s3_bucket_success(self):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True

        params = {
            "guided": False,
            "resolve_s3": False,
            "s3_bucket": True,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_context.default_map.get.side_effect = _make_ctx_params_side_effect_func({"resolve_s3": False})

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.package_option_validation()

    def test_has_no_ZIP_package_type_success(self):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = False

        params = {
            "guided": False,
            "resolve_s3": False,
            "s3_bucket": False,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_context.default_map.get.return_value = {}

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.package_option_validation()

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_validation_failure_has_assets_of_ZIP_package_type(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True

        params = {
            "guided": False,
            "resolve_s3": False,
            "s3_bucket": False,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_context.default_map.get.return_value = {}

        projector_validator = IacProjectValidator(mock_context, project_mock)

        with self.assertRaises(PackageResolveS3AndS3NotSetError) as ex:
            projector_validator.package_option_validation()
        self.assertIn(
            "Cannot skip both --resolve-s3 and --s3-bucket parameters. Please provide one of these arguments.",
            ex.exception.message,
        )

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_validation_failure_both_s3_bucket_and_resolve_s3_provided(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True

        params = {
            "guided": False,
            "resolve_s3": True,
            "s3_bucket": True,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)
        mock_context.default_map.get.return_value = {}

        projector_validator = IacProjectValidator(mock_context, project_mock)

        with self.assertRaises(PackageResolveS3AndS3SetError) as ex:
            projector_validator.package_option_validation()
        self.assertIn(
            "Cannot use both --resolve-s3 and --s3-bucket parameters. Please use only one.", ex.exception.message
        )


class TestImageRepositoryValidation(TestCase):
    def test_image_repository_validation_success_ZIP(self):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = False

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": False,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.image_repository_validation()

    def test_image_repository_validation_success_IMAGE_image_repository(self):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id.return_value = "HelloWorldFunction"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock]

        params = {
            "guided": False,
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "image_repositories": False,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.image_repository_validation()

    def test_image_repository_validation_success_IMAGE_image_repositories(self):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock]

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.image_repository_validation()

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_image_repository_validation_failure_IMAGE_image_repositories_and_image_repository(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": False,
            "image_repository": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            "image_repositories": {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)

        with self.assertRaises(click.BadOptionUsage) as ex:
            projector_validator.image_repository_validation()
        self.assertIn("'--image-repositories' and '--image-repository' cannot be provided", ex.exception.message)

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_image_repository_validation_failure_IMAGE_image_repositories_incomplete(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        function2_mock = MagicMock()
        function2_mock.item_id = "HelloWorldFunction2"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock, function2_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)

        with self.assertRaises(click.BadOptionUsage) as ex:
            projector_validator.image_repository_validation()
        self.assertIn("Incomplete list of function logical ids specified", ex.exception.message)

    @patch("samcli.commands._utils.iac_project_validator.click")
    def test_image_repository_validation_failure_IMAGE_missing_image_repositories(self, mock_click):
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        function2_mock = MagicMock()
        function2_mock.item_id = "HelloWorldFunction2"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock, function2_mock]
        mock_click.BadOptionUsage = click.BadOptionUsage

        params = {
            "guided": False,
            "image_repository": False,
            "image_repositories": None,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)

        with self.assertRaises(click.BadOptionUsage) as ex:
            projector_validator.image_repository_validation()
        self.assertIn("Missing option '--image-repository' or '--image-repositories'", ex.exception.message)

    def test_image_repository_validation_success_missing_image_repositories_guided(self):
        # Guided allows for filling of the image repository values.
        project_mock = MagicMock()
        stack_mock = MagicMock()
        project_mock.stacks = [stack_mock]
        stack_mock.has_assets_of_package_type.return_value = True
        function_mock = MagicMock()
        function_mock.item_id = "HelloWorldFunction"
        function2_mock = MagicMock()
        function2_mock.item_id = "HelloWorldFunction2"
        stack_mock.find_function_resources_of_package_type.return_value = [function_mock, function2_mock]

        params = {
            "guided": True,
            "image_repository": False,
            "image_repositories": None,
            "project_type": "CFN",
            "stack_name": None,
        }
        mock_context = MagicMock()
        mock_context.params.get.side_effect = _make_ctx_params_side_effect_func(params)

        projector_validator = IacProjectValidator(mock_context, project_mock)
        projector_validator.image_repository_validation()
