from unittest import TestCase
from unittest.mock import patch, MagicMock

import click
import posixpath
from parameterized import parameterized

from samcli.lib.cli_validation.image_repository_validation import (
    image_repository_validation,
    _is_all_image_funcs_provided,
)
from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.packagetype import ZIP, IMAGE


class TestImageRepositoryValidation(TestCase):
    def setUp(self):
        @image_repository_validation
        def foo():
            pass

        self.foobar = foo

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_ZIP(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        mock_artifacts.return_value = [ZIP]
        is_all_image_funcs_provided_mock.return_value = True
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [False, False, False, False, False, None, MagicMock()]
        mock_click.get_current_context.return_value = mock_context

        self.foobar()

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_IMAGE_image_repository(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        mock_artifacts.return_value = [IMAGE]
        is_all_image_funcs_provided_mock.return_value = True
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            False,
            False,
            None,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context

        self.foobar()

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_IMAGE_image_repositories(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        mock_artifacts.return_value = [IMAGE]
        is_all_image_funcs_provided_mock.return_value = True
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            False,
            {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            False,
            None,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context
        self.foobar()

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_failure_IMAGE_image_repositories_and_image_repository(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        is_all_image_funcs_provided_mock.return_value = True
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1",
            {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            False,
            None,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar()
        self.assertIn(
            "Only one of the following can be provided: '--image-repositories', '--image-repository', or '--resolve-image-repos'. ",
            ex.exception.message,
        )

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_failure_IMAGE_image_repositories_incomplete(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        is_all_image_funcs_provided_mock.return_value = False
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [
            False,
            False,
            False,
            {"HelloWorldFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
            False,
            None,
            MagicMock(),
        ]
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar()
        self.assertIn("Incomplete list of function logical ids specified", ex.exception.message)

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_failure_IMAGE_missing_image_repositories(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        is_all_image_funcs_provided_mock.return_value = False
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [False, False, False, None, False, None, MagicMock()]
        mock_click.get_current_context.return_value = mock_context

        with self.assertRaises(click.BadOptionUsage) as ex:
            self.foobar()
        self.assertIn(
            "Missing option '--image-repository', '--image-repositories', or '--resolve-image-repos'",
            ex.exception.message,
        )

    @patch("samcli.lib.cli_validation.image_repository_validation.click")
    @patch("samcli.lib.cli_validation.image_repository_validation._is_all_image_funcs_provided")
    @patch("samcli.lib.cli_validation.image_repository_validation.get_template_artifacts_format")
    def test_image_repository_validation_success_missing_image_repositories_guided(
        self, mock_artifacts, is_all_image_funcs_provided_mock, mock_click
    ):
        # Guided allows for filling of the image repository values.
        mock_click.BadOptionUsage = click.BadOptionUsage
        mock_artifacts.return_value = [IMAGE]
        is_all_image_funcs_provided_mock.return_value = False
        mock_context = MagicMock()
        mock_context.params.get.side_effect = [True, True, False, None, False, None, MagicMock()]
        mock_click.get_current_context.return_value = mock_context
        self.foobar()


class TestIsAllImageFunctionsProvided(TestCase):
    @parameterized.expand(
        [
            # CFN Templates
            (
                # no image functions
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                            }
                        },
                    ),
                ],
                None,
                True,
            ),
            (
                # provide a repo for non image function
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                            }
                        },
                    ),
                ],
                {"ServerlessFunc": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
                False,
            ),
            (
                # provide a repo for an invalid function
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                            }
                        },
                    ),
                ],
                {"func1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
                False,
            ),
            (
                # provide all required repos
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "ServerlessImageFunc": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFunc",
                    "LambdaImageFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction",
                },
                True,
            ),
            (
                # missing all required repos
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {},
                False,
            ),
            (
                # missing one required repos
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "LambdaImageFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction",
                },
                False,
            ),
            (
                # provide extra repo
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "ServerlessImageFunc": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFunc",
                    "LambdaImageFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction",
                    "func": "123456789012.dkr.ecr.us-east-1.amazonaws.com/func",
                },
                False,
            ),
            (
                # nested stacks
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFuncInChild": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunctionInChild": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFuncInChild": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunctionInChild": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "ServerlessImageFunc": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFunc",
                    "LambdaImageFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction",
                    "ServerlessImageFuncInChild": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFuncInChild",
                    "LambdaImageFunctionInChild": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild",
                },
                True,
            ),
            (
                # use full path for function repos
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFuncInChild": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunctionInChild": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFuncInChild": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunctionInChild": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "ServerlessImageFunc": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFunc",
                    "LambdaImageFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction",
                    posixpath.join(
                        "childStack", "ServerlessImageFuncInChild"
                    ): "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFuncInChild",
                    posixpath.join(
                        "childStack", "LambdaImageFunctionInChild"
                    ): "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild",
                },
                True,
            ),
            (
                # use mix of full path and logical ids
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFunc": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunction": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "ServerlessFuncInChild": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "CodeUri": ".",
                                    },
                                },
                                "LambdaFunctionInChild": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                },
                                "ServerlessImageFuncInChild": {
                                    "Type": "AWS::Serverless::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "ImageUri": ".",
                                        "PackageType": "Image",
                                    },
                                },
                                "LambdaImageFunctionInChild": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "Handler": "lambda.handler",
                                        "Runtime": "nodejs10.x",
                                        "Code": {"ImageUri": "."},
                                        "PackageType": "Image",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "ServerlessImageFunc": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFunc",
                    "LambdaImageFunction": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction",
                    "ServerlessImageFuncInChild": "123456789012.dkr.ecr.us-east-1.amazonaws.com/ServerlessImageFuncInChild",
                    posixpath.join(
                        "childStack", "LambdaImageFunctionInChild"
                    ): "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild",
                },
                True,
            ),
            # Normalized CDK Template
            (
                # no image functions
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                            }
                        },
                    ),
                ],
                None,
                True,
            ),
            (
                # provide a repo for non image function
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {"LambdaFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
                False,
            ),
            (
                # provide a repo for non image function using resource CDK Id
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {"CDKLambdaFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"},
                False,
            ),
            (
                # provide all required repos
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "LambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "LambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                },
                True,
            ),
            (
                # provide all required repos using resource CDK Ids
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "CDKLambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "CDKLambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                },
                True,
            ),
            (
                # provide all required repos using mix of resource CDK Ids and logical ids
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "LambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "CDKLambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                },
                True,
            ),
            (
                # missing all required repos
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {},
                False,
            ),
            (
                # nested stacks
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "LambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "LambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                    "LambdaImageFunctionInChild1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild1",
                    "LambdaImageFunctionInChild2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild2",
                },
                True,
            ),
            (
                # use CDK Ids
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "CDKLambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "CDKLambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                    "CDKLambdaImageFunctionInChild1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild1",
                    "CDKLambdaImageFunctionInChild2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild2",
                },
                True,
            ),
            (
                # use full paths
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "CDKLambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "CDKLambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                    posixpath.join(
                        "childStack", "CDKLambdaImageFunctionInChild1"
                    ): "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild1",
                    posixpath.join(
                        "childStack", "CDKLambdaImageFunctionInChild2"
                    ): "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild2",
                },
                True,
            ),
            (
                # use mix full ids, cdk ids, and logical ids
                [
                    Stack(
                        "",
                        "",
                        "template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunction1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunction2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunction2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunction2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunction2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                    Stack(
                        "",
                        "childStack",
                        "childStack/template.yaml",
                        {},
                        {
                            "Resources": {
                                "LambdaFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {"Handler": "lambda.handler", "Runtime": "nodejs10.x", "Code": "."},
                                    "Metadata": {
                                        "SamResource": "CDKLambdaFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:property": "Code",
                                    },
                                },
                                "LambdaImageFunctionInChild1": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild1"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild1",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild1/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                                "LambdaImageFunctionInChild2": {
                                    "Type": "AWS::Lambda::Function",
                                    "Properties": {
                                        "PackageType": "Image",
                                        "Code": {"ImageUri": "LambdaImageFunctionInChild2"},
                                    },
                                    "Metadata": {
                                        "SamResource": "CDKLambdaImageFunctionInChild2",
                                        "aws:cdk:path": "Stack/CDKLambdaImageFunctionInChild2/Resource",
                                        "aws:asset:path": ".",
                                        "aws:asset:dockerfile-path": "DockerFile",
                                        "aws:asset:docker-build-args": {},
                                        "aws:asset:property": "Code.ImageUri",
                                    },
                                },
                            }
                        },
                    ),
                ],
                {
                    "CDKLambdaImageFunction1": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction1",
                    "LambdaImageFunction2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunction2",
                    posixpath.join(
                        "childStack", "CDKLambdaImageFunctionInChild1"
                    ): "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild1",
                    "CDKLambdaImageFunctionInChild2": "123456789012.dkr.ecr.us-east-1.amazonaws.com/LambdaImageFunctionInChild2",
                },
                True,
            ),
        ]
    )
    @patch.object(SamLocalStackProvider, "get_stacks")
    def test_is_all_image_functions_provided(self, stacks, input_image_repos, expected_result, get_stacks_mock):
        get_stacks_mock.return_value = stacks, ""
        output = _is_all_image_funcs_provided("", input_image_repos, {})
        self.assertEqual(output, expected_result)
