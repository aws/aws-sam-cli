import os
import posixpath
from unittest import TestCase
from unittest.mock import patch, PropertyMock, Mock, call

from parameterized import parameterized

from samcli.lib.utils.architecture import X86_64, ARM64

from samcli.commands.local.cli_common.user_exceptions import InvalidLayerVersionArn
from samcli.lib.providers.provider import Function, LayerVersion, Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider, RefreshableSamFunctionProvider
from samcli.lib.providers.exceptions import InvalidLayerReference
from samcli.lib.utils.packagetype import IMAGE, ZIP


def make_root_stack(template, parameter_overrides=None):
    return Stack("", "", "template.yaml", parameter_overrides, template)


STACK_PATH = posixpath.join("this_is_a", "stack_path")
STACK = Mock(stack_path=STACK_PATH, location="./template.yaml")


class TestSamFunctionProviderEndToEnd(TestCase):
    """
    Test all public methods with an input template and its child templates
    """

    TEMPLATE = {
        "Resources": {
            "SamFunctions": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFunc1",
                    "CodeUri": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFuncWithInlineCode": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFuncWithInlineCode",
                    "InlineCode": "testcode",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFunc2": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": "s3://bucket/key",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFunc3": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": {"Bucket": "bucket", "Key": "key"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFuncWithFunctionNameOverride": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFuncWithFunctionNameOverride-x",
                    "CodeUri": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFuncWithImage1": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "PackageType": IMAGE,
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "SamFuncWithImage2": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "ImageUri": "image:tag",
                    "PackageType": IMAGE,
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "SamFuncWithImage3": {
                # ImageUri is unsupported ECR location
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo:myimage",
                    "PackageType": IMAGE,
                },
            },
            "SamFuncWithImage4": {
                # ImageUri is unsupported ECR location, but metadata is still provided, build
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo:myimage",
                    "PackageType": IMAGE,
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "LambdaFunc1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"S3Bucket": "bucket", "S3Key": "key"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "LambdaFuncWithImage1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "PackageType": IMAGE,
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "LambdaFuncWithImage2": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"ImageUri": "image:tag"},
                    "PackageType": IMAGE,
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "LambdaFuncWithImage3": {
                # ImageUri is unsupported ECR location
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo"},
                    "PackageType": IMAGE,
                },
            },
            "LambdaFuncWithImage4": {
                # ImageUri is unsupported ECR location, but metadata is still provided, build
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo"},
                    "PackageType": IMAGE,
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "LambdaFuncWithInlineCode": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"ZipFile": "testcode"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "LambdaFuncWithLocalPath": {
                "Type": "AWS::Lambda::Function",
                "Properties": {"Code": "./some/path/to/code", "Runtime": "nodejs4.3", "Handler": "index.handler"},
            },
            "LambdaFuncWithFunctionNameOverride": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "FunctionName": "LambdaFuncWithFunctionNameOverride-x",
                    "Code": "./some/path/to/code",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "LambdaFuncWithCodeSignConfig": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "FunctionName": "LambdaFuncWithCodeSignConfig",
                    "Code": "./some/path/to/code",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                    "CodeSigningConfigArn": "codeSignConfigArn",
                },
            },
            "LambdaFuncWithCustomId": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
                "Metadata": {"SamResourceId": "LambdaFunctionCustomId-x"},
            },
            "LambdaCDKFunc": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"Bucket": "bucket", "Key": "key"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
                "Metadata": {
                    "aws:cdk:path": "Stack/LambdaCFKFunction-x/Resource",
                    "aws:asset:path": "/usr/foo/bar",
                    "aws:asset:property": "Code",
                },
            },
            "OtherResource": {
                "Type": "AWS::Serverless::Api",
                "Properties": {"StageName": "prod", "DefinitionUri": "s3://bucket/key"},
            },
            "ChildStack": {
                "Type": "AWS::Serverless::Application",
                "Properties": {"Location": "./child.yaml"},
            },
        }
    }

    CHILD_TEMPLATE = {
        "Resources": {
            "SamFunctionsInChild": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFunctionsInChildName",
                    "CodeUri": "./foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamFunctionsInChildAbsPath": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "FunctionName": "SamFunctionsInChildAbsPathName",
                    "CodeUri": "/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
            },
            "SamImageFunctionsInChild": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "PackageType": "Image",
                },
                "Metadata": {"DockerTag": "tag", "DockerContext": "./image", "Dockerfile": "Dockerfile"},
            },
            "LambdaCDKFuncInChild": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {"Bucket": "bucket", "Key": "key"},
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler",
                },
                "Metadata": {
                    "aws:cdk:path": "Stack/LambdaCDKFuncInChild-x/Resource",
                    "aws:asset:path": "/usr/foo/bar",
                    "aws:asset:property": "Code",
                },
            },
        }
    }

    def setUp(self):
        self.parameter_overrides = {}
        root_stack = Stack("", "", "template.yaml", self.parameter_overrides, self.TEMPLATE)
        child_stack = Stack("", "ChildStack", "./child/template.yaml", None, self.CHILD_TEMPLATE)
        with patch("samcli.lib.providers.sam_stack_provider.get_template_data") as get_template_data_mock:
            get_template_data_mock.side_effect = lambda t: {
                "template.yaml": self.TEMPLATE,
                "./child/template.yaml": self.CHILD_TEMPLATE,
            }
            self.provider = SamFunctionProvider([root_stack, child_stack])

    @parameterized.expand(
        [
            (
                "SamFunc1",
                Function(
                    function_id="SamFunctions",
                    name="SamFunctions",
                    functionname="SamFunc1",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "SamFunctions"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "SamFuncWithInlineCode",
                Function(
                    function_id="SamFuncWithInlineCode",
                    name="SamFuncWithInlineCode",
                    functionname="SamFuncWithInlineCode",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=None,
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "SamFuncWithInlineCode"},
                    inlinecode="testcode",
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "SamFunctions",
                Function(
                    function_id="SamFunctions",
                    name="SamFunctions",
                    functionname="SamFunc1",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "SamFunctions"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            ("SamFunc2", None),  # codeuri is a s3 location, ignored
            ("SamFunc3", None),  # codeuri is a s3 location, ignored
            (
                "SamFuncWithImage1",
                Function(
                    function_id="SamFuncWithImage1",
                    name="SamFuncWithImage1",
                    functionname="SamFuncWithImage1",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=IMAGE,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("image"),
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "SamFuncWithImage1",
                    },
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "SamFuncWithImage2",
                Function(
                    function_id="SamFuncWithImage2",
                    name="SamFuncWithImage2",
                    functionname="SamFuncWithImage2",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    inlinecode=None,
                    imageuri="image:tag",
                    imageconfig=None,
                    packagetype=IMAGE,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("image"),
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "SamFuncWithImage2",
                    },
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            ("SamFuncWithImage3", None),  # imageuri is ecr location, ignored
            (
                "SamFuncWithImage4",  # despite imageuri is ecr location, the necessary metadata is still provided, build
                Function(
                    function_id="SamFuncWithImage4",
                    name="SamFuncWithImage4",
                    functionname="SamFuncWithImage4",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    inlinecode=None,
                    imageuri="123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo:myimage",
                    imageconfig=None,
                    packagetype=IMAGE,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("image"),
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "SamFuncWithImage4",
                    },
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "SamFuncWithFunctionNameOverride-x",
                Function(
                    function_id="SamFuncWithFunctionNameOverride",
                    name="SamFuncWithFunctionNameOverride",
                    functionname="SamFuncWithFunctionNameOverride-x",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "SamFuncWithFunctionNameOverride"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            ("LambdaFunc1", None),  # codeuri is a s3 location, ignored
            (
                "LambdaFuncWithImage1",
                Function(
                    function_id="LambdaFuncWithImage1",
                    name="LambdaFuncWithImage1",
                    functionname="LambdaFuncWithImage1",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("image"),
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "LambdaFuncWithImage1",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=IMAGE,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaFuncWithImage2",
                Function(
                    function_id="LambdaFuncWithImage2",
                    name="LambdaFuncWithImage2",
                    functionname="LambdaFuncWithImage2",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("image"),
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "LambdaFuncWithImage2",
                    },
                    inlinecode=None,
                    imageuri="image:tag",
                    imageconfig=None,
                    packagetype=IMAGE,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            ("LambdaFuncWithImage3", None),  # imageuri is a ecr location, ignored
            (
                "LambdaFuncWithImage4",  # despite imageuri is ecr location, the necessary metadata is still provided, build
                Function(
                    function_id="LambdaFuncWithImage4",
                    name="LambdaFuncWithImage4",
                    functionname="LambdaFuncWithImage4",
                    runtime=None,
                    handler=None,
                    codeuri=".",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("image"),
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "LambdaFuncWithImage4",
                    },
                    inlinecode=None,
                    imageuri="123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo",
                    imageconfig=None,
                    packagetype=IMAGE,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaFuncWithInlineCode",
                Function(
                    function_id="LambdaFuncWithInlineCode",
                    name="LambdaFuncWithInlineCode",
                    functionname="LambdaFuncWithInlineCode",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=None,
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "LambdaFuncWithInlineCode"},
                    inlinecode="testcode",
                    codesign_config_arn=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaFuncWithLocalPath",
                Function(
                    function_id="LambdaFuncWithLocalPath",
                    name="LambdaFuncWithLocalPath",
                    functionname="LambdaFuncWithLocalPath",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=os.path.join("some", "path", "to", "code"),
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "LambdaFuncWithLocalPath"},
                    inlinecode=None,
                    codesign_config_arn=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaFuncWithFunctionNameOverride-x",
                Function(
                    function_id="LambdaFuncWithFunctionNameOverride",
                    name="LambdaFuncWithFunctionNameOverride",
                    functionname="LambdaFuncWithFunctionNameOverride-x",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=os.path.join("some", "path", "to", "code"),
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "LambdaFuncWithFunctionNameOverride"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaFuncWithCodeSignConfig",
                Function(
                    function_id="LambdaFuncWithCodeSignConfig",
                    name="LambdaFuncWithCodeSignConfig",
                    functionname="LambdaFuncWithCodeSignConfig",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=os.path.join("some", "path", "to", "code"),
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "LambdaFuncWithCodeSignConfig"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn="codeSignConfigArn",
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                posixpath.join("ChildStack", "SamFunctionsInChild"),
                Function(
                    function_id="SamFunctionsInChild",
                    name="SamFunctionsInChild",
                    functionname="SamFunctionsInChildName",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri=os.path.join("child", "foo", "bar"),
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "SamFunctionsInChild"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="ChildStack",
                ),
            ),
            (
                posixpath.join("ChildStack", "SamFunctionsInChildAbsPath"),
                Function(
                    function_id="SamFunctionsInChildAbsPath",
                    name="SamFunctionsInChildAbsPath",
                    functionname="SamFunctionsInChildAbsPathName",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "SamFunctionsInChildAbsPath"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="ChildStack",
                ),
            ),
            (
                posixpath.join("ChildStack", "SamImageFunctionsInChild"),
                Function(
                    function_id="SamImageFunctionsInChild",
                    name="SamImageFunctionsInChild",
                    functionname="SamImageFunctionsInChild",
                    runtime=None,
                    handler=None,
                    codeuri="child",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "DockerTag": "tag",
                        "DockerContext": os.path.join("child", "image"),  # the path should starts with child
                        "Dockerfile": "Dockerfile",
                        "SamResourceId": "SamImageFunctionsInChild",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=IMAGE,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="ChildStack",
                ),
            ),
            (
                "LambdaFunctionCustomId-x",
                Function(
                    function_id="LambdaFunctionCustomId-x",
                    name="LambdaFuncWithCustomId",
                    functionname="LambdaFuncWithCustomId",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "LambdaFunctionCustomId-x"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaFuncWithCustomId",
                Function(
                    function_id="LambdaFunctionCustomId-x",
                    name="LambdaFuncWithCustomId",
                    functionname="LambdaFuncWithCustomId",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={"SamResourceId": "LambdaFunctionCustomId-x"},
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaCFKFunction-x",
                Function(
                    function_id="LambdaCFKFunction-x",
                    name="LambdaCDKFunc",
                    functionname="LambdaCDKFunc",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "aws:cdk:path": "Stack/LambdaCFKFunction-x/Resource",
                        "aws:asset:path": "/usr/foo/bar",
                        "aws:asset:property": "Code",
                        "SamNormalized": True,
                        "SamResourceId": "LambdaCFKFunction-x",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaCDKFunc",
                Function(
                    function_id="LambdaCFKFunction-x",
                    name="LambdaCDKFunc",
                    functionname="LambdaCDKFunc",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "aws:cdk:path": "Stack/LambdaCFKFunction-x/Resource",
                        "aws:asset:path": "/usr/foo/bar",
                        "aws:asset:property": "Code",
                        "SamNormalized": True,
                        "SamResourceId": "LambdaCFKFunction-x",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="",
                ),
            ),
            (
                "LambdaCDKFuncInChild-x",
                Function(
                    function_id="LambdaCDKFuncInChild-x",
                    name="LambdaCDKFuncInChild",
                    functionname="LambdaCDKFuncInChild",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "aws:cdk:path": "Stack/LambdaCDKFuncInChild-x/Resource",
                        "aws:asset:path": "/usr/foo/bar",
                        "aws:asset:property": "Code",
                        "SamNormalized": True,
                        "SamResourceId": "LambdaCDKFuncInChild-x",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="ChildStack",
                ),
            ),
            (
                "LambdaCDKFuncInChild",
                Function(
                    function_id="LambdaCDKFuncInChild-x",
                    name="LambdaCDKFuncInChild",
                    functionname="LambdaCDKFuncInChild",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "aws:cdk:path": "Stack/LambdaCDKFuncInChild-x/Resource",
                        "aws:asset:path": "/usr/foo/bar",
                        "aws:asset:property": "Code",
                        "SamNormalized": True,
                        "SamResourceId": "LambdaCDKFuncInChild-x",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="ChildStack",
                ),
            ),
            (
                posixpath.join("ChildStack", "LambdaCDKFuncInChild-x"),
                Function(
                    function_id="LambdaCDKFuncInChild-x",
                    name="LambdaCDKFuncInChild",
                    functionname="LambdaCDKFuncInChild",
                    runtime="nodejs4.3",
                    handler="index.handler",
                    codeuri="/usr/foo/bar",
                    memory=None,
                    timeout=None,
                    environment=None,
                    rolearn=None,
                    layers=[],
                    events=None,
                    metadata={
                        "aws:cdk:path": "Stack/LambdaCDKFuncInChild-x/Resource",
                        "aws:asset:path": "/usr/foo/bar",
                        "aws:asset:property": "Code",
                        "SamNormalized": True,
                        "SamResourceId": "LambdaCDKFuncInChild-x",
                    },
                    inlinecode=None,
                    imageuri=None,
                    imageconfig=None,
                    packagetype=ZIP,
                    codesign_config_arn=None,
                    architectures=None,
                    stack_path="ChildStack",
                ),
            ),
            (
                # resource_Iac_id is used to build full_path, so logical id will not be used in full_path if
                # resource_iac_id exists
                posixpath.join("ChildStack", "LambdaCDKFuncInChild"),
                None,
            ),
        ]
    )
    def test_get_must_return_each_function(self, name, expected_output):

        actual = self.provider.get(name)
        self.assertEqual(actual, expected_output)

    def test_get_all_must_return_all_functions(self):

        result = {f.full_path for f in self.provider.get_all()}
        expected = {
            "SamFunctions",
            "SamFuncWithImage1",
            "SamFuncWithImage2",
            "SamFuncWithImage4",
            "SamFuncWithInlineCode",
            "SamFuncWithFunctionNameOverride",
            "LambdaFuncWithImage1",
            "LambdaFuncWithImage2",
            "LambdaFuncWithImage4",
            "LambdaFuncWithInlineCode",
            "LambdaFuncWithLocalPath",
            "LambdaFuncWithFunctionNameOverride",
            "LambdaFuncWithCodeSignConfig",
            "LambdaFunctionCustomId-x",
            "LambdaCFKFunction-x",
            posixpath.join("ChildStack", "SamFunctionsInChild"),
            posixpath.join("ChildStack", "SamFunctionsInChildAbsPath"),
            posixpath.join("ChildStack", "SamImageFunctionsInChild"),
            posixpath.join("ChildStack", "LambdaCDKFuncInChild-x"),
        }

        self.assertEqual(expected, result)


class TestSamFunctionProvider_init(TestCase):
    def setUp(self):
        self.parameter_overrides = {}

    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_must_extract_functions(self, get_template_mock, extract_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        provider = SamFunctionProvider([stack])

        extract_mock.assert_called_with([stack], False, False)
        get_template_mock.assert_called_with(template, self.parameter_overrides)
        self.assertEqual(provider.functions, extract_result)

    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_must_default_to_empty_resources(self, get_template_mock, extract_mock):
        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"a": "b"}  # Template does *not* have 'Resources' key
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        provider = SamFunctionProvider([stack])

        extract_mock.assert_called_with([stack], False, False)  # Empty Resources value must be passed
        self.assertEqual(provider.functions, extract_result)


class TestSamFunctionProvider_extract_functions(TestCase):
    @patch("samcli.lib.providers.sam_function_provider.Stack.resources", new_callable=PropertyMock)
    @patch.object(SamFunctionProvider, "_convert_sam_function_resource")
    def test_must_work_for_sam_function(self, convert_mock, resources_mock):
        convertion_result = Mock()
        convertion_result.full_path = "A/B/C/Func1"
        convert_mock.return_value = convertion_result

        resources_mock.return_value = {"Func1": {"Type": "AWS::Serverless::Function", "Properties": {"a": "b"}}}
        expected = {"A/B/C/Func1": convertion_result}

        stack = make_root_stack(None)
        result = SamFunctionProvider._extract_functions([stack])
        self.assertEqual(expected, result)
        convert_mock.assert_called_with(stack, "Func1", {"a": "b"}, [], False)

    @patch("samcli.lib.providers.sam_function_provider.Stack.resources", new_callable=PropertyMock)
    @patch.object(SamFunctionProvider, "_convert_sam_function_resource")
    def test_must_work_with_no_properties(self, convert_mock, resources_mock):
        convertion_result = Mock()
        convertion_result.full_path = "A/B/C/Func1"
        convert_mock.return_value = convertion_result

        resources_mock.return_value = {
            "Func1": {
                "Type": "AWS::Serverless::Function"
                # No Properties
            }
        }

        expected = {"A/B/C/Func1": convertion_result}

        stack = make_root_stack(None)
        result = SamFunctionProvider._extract_functions([stack])
        self.assertEqual(expected, result)
        convert_mock.assert_called_with(
            stack,
            "Func1",
            {},
            [],
            False,
        )

    @patch("samcli.lib.providers.sam_function_provider.Stack.resources", new_callable=PropertyMock)
    @patch.object(SamFunctionProvider, "_convert_lambda_function_resource")
    def test_must_work_for_lambda_function(self, convert_mock, resources_mock):
        convertion_result = Mock()
        convertion_result.full_path = "A/B/C/Func1"
        convert_mock.return_value = convertion_result

        resources_mock.return_value = {"Func1": {"Type": "AWS::Lambda::Function", "Properties": {"a": "b"}}}

        expected = {"A/B/C/Func1": convertion_result}

        stack = make_root_stack(None)
        result = SamFunctionProvider._extract_functions([stack])
        self.assertEqual(expected, result)
        convert_mock.assert_called_with(stack, "Func1", {"a": "b"}, [], False)

    @patch("samcli.lib.providers.sam_function_provider.Stack.resources", new_callable=PropertyMock)
    def test_must_skip_unknown_resource(self, resources_mock):
        resources_mock.return_value = {"Func1": {"Type": "AWS::SomeOther::Function", "Properties": {"a": "b"}}}

        expected = {}

        result = SamFunctionProvider._extract_functions([make_root_stack(None)])
        self.assertEqual(expected, result)

    @patch.object(SamFunctionProvider, "_convert_lambda_function_resource")
    def test_must_work_for_multiple_functions_with_name_but_in_different_stacks(
        self,
        convert_mock,
    ):
        function_root = Mock()
        function_root.name = "Func1"
        function_root.full_path = "Func1"
        function_child = Mock()
        function_child.name = "Func1"
        function_child.full_path = "C/Func1"

        stack_root = Mock()
        stack_root.resources = {
            "Func1": {"Type": "AWS::Lambda::Function", "Properties": {"a": "b"}},
            "C": {"Type": "AWS::Serverless::Application", "Properties": {"Location": "./child.yaml"}},
        }
        stack_child = Mock()
        stack_child.resources = {
            "Func1": {"Type": "AWS::Lambda::Function", "Properties": {"a": "b"}},
        }

        convert_mock.side_effect = [function_root, function_child]

        expected = {"Func1": function_root, "C/Func1": function_child}

        result = SamFunctionProvider._extract_functions([stack_root, stack_child])
        self.assertEqual(expected, result)
        convert_mock.assert_has_calls(
            [
                call(stack_root, "Func1", {"a": "b"}, [], False),
                call(stack_child, "Func1", {"a": "b"}, [], False),
            ]
        )


class TestSamFunctionProvider_get_function_id(TestCase):
    def test_get_default_logical_id_no_property(self):
        resource_properties = {
            "CodeUri": "/usr/local",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
            "Architectures": [X86_64],
            "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
        }
        logical_id = "DefaultLogicalId"

        result = SamFunctionProvider._get_function_id(resource_properties=resource_properties, logical_id=logical_id)
        expected = logical_id
        self.assertEqual(expected, result)

    def test_get_default_logical_id_property_empty_str(self):
        resource_properties = {
            "CodeUri": "/usr/local",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
            "Architectures": [X86_64],
            "Metadata": {
                "aws:asset:path": "new path",
                "aws:asset:property": "Code",
                "aws:cdk:path": "",
                "SamResourceId": "",
            },
        }
        logical_id = "DefaultLogicalId"

        result = SamFunctionProvider._get_function_id(resource_properties=resource_properties, logical_id=logical_id)
        expected = logical_id
        self.assertEqual(expected, result)

    def test_get_function_id(self):
        resource_properties = {
            "CodeUri": "/usr/local",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
            "Architectures": [X86_64],
            "Metadata": {
                "aws:asset:path": "new path",
                "aws:asset:property": "Code",
                "aws:cdk:path": "stack/functionId/Resource",
                "SamResourceId": "functionId",
            },
        }
        logical_id = "DefaultLogicalId"

        result = SamFunctionProvider._get_function_id(resource_properties=resource_properties, logical_id=logical_id)
        expected = "functionId"
        self.assertEqual(expected, result)


class TestSamFunctionProvider_convert_sam_function_resource(TestCase):
    def test_must_convert_zip(self):

        name = "myname"
        properties = {
            "CodeUri": "/usr/local",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
            "Architectures": [X86_64],
        }

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri="/usr/local",
            environment="myenvironment",
            rolearn="myrole",
            layers=["Layer1", "Layer2"],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=[X86_64],
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, ["Layer1", "Layer2"])

        self.assertEqual(expected, result)

    def test_must_convert_image(self):

        name = "myname"
        properties = {
            "ImageUri": "helloworld:v1",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "ImageConfig": {"WorkingDirectory": "/var/task", "Command": "/bin/bash", "EntryPoint": "echo Hello!"},
            "PackageType": IMAGE,
        }

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri=".",
            environment="myenvironment",
            rolearn="myrole",
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri="helloworld:v1",
            imageconfig={"WorkingDirectory": "/var/task", "Command": "/bin/bash", "EntryPoint": "echo Hello!"},
            packagetype=IMAGE,
            codesign_config_arn=None,
            architectures=None,
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, [])

        self.assertEqual(expected, result)

    def test_must_skip_non_existent_properties(self):

        name = "myname"
        properties = {"CodeUri": "/usr/local"}

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime=None,
            memory=None,
            timeout=None,
            handler=None,
            codeuri="/usr/local",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=None,
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, [])

        self.assertEqual(expected, result)

    def test_must_default_missing_code_uri(self):

        name = "myname"
        properties = {"Runtime": "myruntime"}

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, [])
        self.assertEqual(result.codeuri, ".")  # Default value

    def test_must_use_inlinecode(self):

        name = "myname"
        properties = {
            "InlineCode": "testcode",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "index.handler",
            "Architectures": [X86_64],
        }

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="index.handler",
            codeuri=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode="testcode",
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=[X86_64],
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, [])

        self.assertEqual(expected, result)

    def test_must_prioritize_inlinecode(self):

        name = "myname"
        properties = {
            "CodeUri": "/usr/local",
            "InlineCode": "testcode",
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "index.handler",
            "Architectures": [ARM64],
        }

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="index.handler",
            codeuri=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode="testcode",
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=[ARM64],
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, [])

        self.assertEqual(expected, result)

    def test_must_handle_code_dict(self):

        name = "myname"
        properties = {
            "CodeUri": {
                # CodeUri is some dictionary
                "a": "b"
            }
        }

        result = SamFunctionProvider._convert_sam_function_resource(STACK, name, properties, [])
        self.assertEqual(result.codeuri, ".")  # Default value


class TestSamFunctionProvider_convert_lambda_function_resource(TestCase):
    def test_must_convert(self):

        name = "myname"
        properties = {
            "Code": {"Bucket": "bucket"},
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Role": "myrole",
            "Layers": ["Layer1", "Layer2"],
        }

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri=".",
            environment="myenvironment",
            rolearn="myrole",
            layers=["Layer1", "Layer2"],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=None,
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_lambda_function_resource(STACK, name, properties, ["Layer1", "Layer2"])

        self.assertEqual(expected, result)

    def test_must_use_inlinecode(self):

        name = "myname"
        properties = {
            "Code": {"ZipFile": "testcode"},
            "Runtime": "myruntime",
            "MemorySize": "mymemorysize",
            "Timeout": "30",
            "Handler": "myhandler",
            "Environment": "myenvironment",
            "Architectures": [ARM64],
        }

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime="myruntime",
            memory="mymemorysize",
            timeout="30",
            handler="myhandler",
            codeuri=None,
            environment="myenvironment",
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode="testcode",
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=[ARM64],
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_lambda_function_resource(STACK, name, properties, [])

        self.assertEqual(expected, result)

    def test_must_skip_non_existent_properties(self):

        name = "myname"
        properties = {"Code": {"Bucket": "bucket"}}

        expected = Function(
            function_id="myname",
            name="myname",
            functionname="myname",
            runtime=None,
            memory=None,
            timeout=None,
            handler=None,
            codeuri=".",
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=ZIP,
            codesign_config_arn=None,
            architectures=None,
            stack_path=STACK_PATH,
        )

        result = SamFunctionProvider._convert_lambda_function_resource(STACK, name, properties, [])

        self.assertEqual(expected, result)


class TestSamFunctionProvider_parse_layer_info(TestCase):
    @parameterized.expand(
        [
            ({"Function": {"Type": "AWS::Serverless::Function", "Properties": {}}}, {"Ref": "Function"}),
            ({}, {"Ref": "LayerDoesNotExist"}),
        ]
    )
    def test_raise_on_invalid_layer_resource(self, resources, layer_reference):
        with self.assertRaises(InvalidLayerReference):
            SamFunctionProvider._parse_layer_info(STACK, [layer_reference], resources)

    @parameterized.expand(
        [
            (
                {"Function": {"Type": "AWS::Serverless::Function", "Properties": {}}},
                "arn:aws:lambda:::awslayer:AmazonLinux1703",
            )
        ]
    )
    def test_raise_on_AmazonLinux1703_layer_provided(self, resources, layer_reference):
        with self.assertRaises(InvalidLayerVersionArn):
            SamFunctionProvider._parse_layer_info(STACK, [layer_reference], resources)

    def test_must_ignore_opt_in_AmazonLinux1803_layer(self):
        resources = {}

        list_of_layers = [
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            "arn:aws:lambda:::awslayer:AmazonLinux1803",
        ]
        actual = SamFunctionProvider._parse_layer_info(
            Mock(stack_path=STACK_PATH, location="template.yaml", resources=resources), list_of_layers
        )

        for (actual_layer, expected_layer) in zip(
            actual, [LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=STACK_PATH)]
        ):
            self.assertEqual(actual_layer, expected_layer)

    def test_layers_created_from_template_resources(self):
        resources = {
            "Layer": {"Type": "AWS::Lambda::LayerVersion", "Properties": {"Content": "/somepath"}},
            "ServerlessLayer": {"Type": "AWS::Serverless::LayerVersion", "Properties": {"ContentUri": "/somepath"}},
        }

        list_of_layers = [
            {"Ref": "Layer"},
            {"Ref": "ServerlessLayer"},
            "arn:aws:lambda:region:account-id:layer:layer-name:1",
            {"NonRef": "Something"},
        ]
        actual = SamFunctionProvider._parse_layer_info(
            Mock(stack_path=STACK_PATH, location="template.yaml", resources=resources), list_of_layers
        )

        for (actual_layer, expected_layer) in zip(
            actual,
            [
                LayerVersion("Layer", "/somepath", stack_path=STACK_PATH),
                LayerVersion("ServerlessLayer", "/somepath", stack_path=STACK_PATH),
                LayerVersion("arn:aws:lambda:region:account-id:layer:layer-name:1", None, stack_path=STACK_PATH),
            ],
        ):
            self.assertEqual(actual_layer, expected_layer)

    def test_return_empty_list_on_no_layers(self):
        resources = {"Function": {"Type": "AWS::Serverless::Function", "Properties": {}}}

        actual = SamFunctionProvider._parse_layer_info(
            Mock(stack_path=STACK_PATH, location="template.yaml", resources=resources), []
        )

        self.assertEqual(actual, [])


class TestSamFunctionProvider_get(TestCase):
    def test_raise_on_invalid_name(self):
        provider = SamFunctionProvider([])

        with self.assertRaises(ValueError):
            provider.get(None)

    def test_must_return_function_value(self):
        provider = SamFunctionProvider([])
        # Cheat a bit here by setting the value of this property directly
        function = Function(
            function_id="not-value",
            name="not-value",
            functionname="value",
            runtime=None,
            handler=None,
            codeuri=None,
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=None,
            codesign_config_arn=None,
            architectures=None,
            stack_path=STACK_PATH,
        )
        provider.functions = {"func1": function}

        self.assertEqual(function, provider.get("value"))

    def test_found_by_different_ids(self):
        provider = SamFunctionProvider([])
        # Cheat a bit here by setting the value of this property directly
        function1 = Function(
            function_id="not-value",
            name="not-value",
            functionname="not-value",
            runtime=None,
            handler=None,
            codeuri=None,
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=None,
            codesign_config_arn=None,
            architectures=None,
            stack_path=posixpath.join("this_is", "stack_path_C"),
        )

        function2 = Function(
            function_id="expected_function_id",
            name="not-value",
            functionname="not-value",
            runtime=None,
            handler=None,
            codeuri=None,
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=None,
            codesign_config_arn=None,
            architectures=None,
            stack_path=posixpath.join("this_is", "stack_path_B"),
        )

        function3 = Function(
            function_id="not-value",
            name="expected_logical_id",
            functionname="not-value",
            runtime=None,
            handler=None,
            codeuri=None,
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=None,
            codesign_config_arn=None,
            architectures=None,
            stack_path=posixpath.join("this_is", "stack_path_A"),
        )

        function4 = Function(
            function_id="not-value",
            name="not-value",
            functionname="expected_function_name",
            runtime=None,
            handler=None,
            codeuri=None,
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[],
            events=None,
            metadata=None,
            inlinecode=None,
            imageuri=None,
            imageconfig=None,
            packagetype=None,
            codesign_config_arn=None,
            architectures=None,
            stack_path=posixpath.join("this_is", "stack_path_D"),
        )
        provider.functions = {"func1": function1, "func2": function2, "func3": function3, "func4": function4}

        self.assertIsNone(provider.get("value"))
        self.assertEqual(function1, provider.get("func1"))
        self.assertEqual(function2, provider.get("expected_function_id"))
        self.assertEqual(function3, provider.get("expected_logical_id"))
        self.assertEqual(function4, provider.get("expected_function_name"))
        # The returned function is the full_path sorted one if multiple ones are matched
        self.assertEqual(function3, provider.get("not-value"))

    def test_return_none_if_function_not_found(self):
        provider = SamFunctionProvider([])

        self.assertIsNone(provider.get("somefunc"), "Must return None when Function is not found")


class TestSamFunctionProvider_get_all(TestCase):
    def test_must_work_with_no_functions(self):
        provider = SamFunctionProvider([])

        result = [f for f in provider.get_all()]
        self.assertEqual(result, [])


class TestRefreshableSamFunctionProvider(TestCase):
    def setUp(self):
        self.parameter_overrides = {}
        self.global_parameter_overrides = {}
        self.file_observer = Mock()
        self.file_observer.start = Mock()
        self.file_observer.watch = Mock()
        self.file_observer.unwatch = Mock()
        self.file_observer.stop = Mock()

    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_init_must_extract_functions_and_stacks_got_observed(
        self, get_template_mock, extract_mock, FileObserverMock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )

        extract_mock.assert_called_with([stack, stack2], False, False)
        get_template_mock.assert_called_with(template, self.parameter_overrides)
        self.assertEqual(provider.functions, extract_result)

        FileObserverMock.assert_called_with(provider._set_templates_changed)
        self.file_observer.start.assert_called_with()
        self.file_observer.watch.assert_has_calls([call("template.yaml"), call("child/template.yaml")])

        self.assertEqual(provider.parent_templates_paths, ["template.yaml"])
        self.assertEqual(provider.is_changed, False)

    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_reload_flag_set_to_true_incase_any_template_got_changed(
        self, get_template_mock, extract_mock, FileObserverMock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )
        provider._set_templates_changed(["child/template.yaml"])

        self.assertTrue(provider.is_changed)
        self.file_observer.unwatch.assert_has_calls([call("template.yaml"), call("child/template.yaml")])

    @patch("samcli.lib.providers.sam_function_provider.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_reload_incase_if_change_flag_is_true_and_stacks_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock, get_stacks_mock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )
        provider._set_templates_changed(["child/template.yaml"])
        updated_template = {"Resources": {"a": "b", "c": "d"}}
        updated_template2 = {"Resources": {"a": "b"}}
        updated_template3 = {"Resources": {"a": "b"}}
        stack = make_root_stack(updated_template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, updated_template2)
        stack3 = Stack("", "childStack2", "child/child/template.yaml", self.parameter_overrides, updated_template3)
        get_stacks_mock.return_value = [stack, stack2, stack3], None

        updated_extract_result = {"foo": "bar", "foo2": "bar2"}
        extract_mock.return_value = updated_extract_result

        self.file_observer.watch.reset_mock()
        stacks = provider.stacks
        self.assertEqual(stacks, [stack, stack2, stack3])
        self.assertFalse(provider.is_changed)

        self.file_observer.watch.assert_has_calls(
            [call("template.yaml"), call("child/template.yaml"), call("child/child/template.yaml")]
        )

        functions = []
        for func in provider.get_all():
            functions.append(func)
        self.assertEqual(functions, ["bar", "bar2"])

    @patch("samcli.lib.providers.sam_function_provider.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_reload_incase_if_change_flag_is_true_and_get_all_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock, get_stacks_mock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )
        provider._set_templates_changed(["child/template.yaml"])
        updated_template = {"Resources": {"a": "b", "c": "d"}}
        updated_template2 = {"Resources": {"a": "b"}}
        updated_template3 = {"Resources": {"a": "b"}}
        stack = make_root_stack(updated_template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, updated_template2)
        stack3 = Stack("", "childStack2", "child/child/template.yaml", self.parameter_overrides, updated_template3)
        get_stacks_mock.return_value = [stack, stack2, stack3], None

        updated_extract_result = {"foo": "bar", "foo2": "bar2"}
        extract_mock.return_value = updated_extract_result

        self.file_observer.watch.reset_mock()

        functions = []
        for func in provider.get_all():
            functions.append(func)
        self.assertEqual(functions, ["bar", "bar2"])
        self.assertFalse(provider.is_changed)

        self.file_observer.watch.assert_has_calls(
            [call("template.yaml"), call("child/template.yaml"), call("child/child/template.yaml")]
        )

    @patch("samcli.lib.providers.sam_function_provider.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_reload_incase_if_change_flag_is_true_and_get_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock, get_stacks_mock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )
        provider._set_templates_changed(["child/template.yaml"])
        updated_template = {"Resources": {"a": "b", "c": "d"}}
        updated_template2 = {"Resources": {"a": "b"}}
        updated_template3 = {"Resources": {"a": "b"}}
        stack = make_root_stack(updated_template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, updated_template2)
        stack3 = Stack("", "childStack2", "child/child/template.yaml", self.parameter_overrides, updated_template3)
        get_stacks_mock.return_value = [stack, stack2, stack3], None

        func1 = Mock()
        func2 = Mock()
        updated_extract_result = {"foo": func1, "foo2": func2}
        extract_mock.return_value = updated_extract_result

        self.file_observer.watch.reset_mock()
        self.assertEqual(provider.get("foo2"), func2)
        self.assertFalse(provider.is_changed)

        self.file_observer.watch.assert_has_calls(
            [call("template.yaml"), call("child/template.yaml"), call("child/child/template.yaml")]
        )

    @patch("samcli.lib.providers.sam_function_provider.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_reload_incase_if_change_flag_is_true_and_get_resources_by_stack_path_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock, get_stacks_mock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )
        provider._set_templates_changed(["child/template.yaml"])
        updated_template = {"Resources": {"a": "b", "c": "d"}}
        updated_template2 = {"Resources": {"a": "b"}}
        updated_template3 = {"Resources": {"c": "d"}}
        get_template_mock.return_value = updated_template
        stack = make_root_stack(updated_template, self.parameter_overrides)
        get_template_mock.return_value = updated_template2
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, updated_template2)
        get_template_mock.return_value = updated_template3
        stack3 = Stack(
            "childStack", "childStack2", "child/child/template.yaml", self.parameter_overrides, updated_template3
        )
        get_stacks_mock.return_value = [stack, stack2, stack3], None

        func1 = Mock()
        func2 = Mock()
        updated_extract_result = {"foo": func1, "foo2": func2}
        extract_mock.return_value = updated_extract_result

        self.file_observer.watch.reset_mock()

        self.assertEqual(provider.get_resources_by_stack_path("childStack/childStack2"), {"c": "d"})
        self.assertFalse(provider.is_changed)

        self.file_observer.watch.assert_has_calls(
            [call("template.yaml"), call("child/template.yaml"), call("child/child/template.yaml")]
        )

    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_does_not_reload_incase_if_change_flag_is_false_and_stacks_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )

        self.file_observer.watch.reset_mock()
        stacks = provider.stacks
        self.assertEqual(stacks, [stack, stack2])
        self.assertFalse(provider.is_changed)

        self.file_observer.watch.assert_not_called()

        functions = []
        for func in provider.get_all():
            functions.append(func)
        self.assertEqual(functions, ["bar"])

    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_does_not_reload_incase_if_change_flag_is_false_and_get_all_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock
    ):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )

        self.file_observer.watch.reset_mock()
        functions = []
        for func in provider.get_all():
            functions.append(func)
        self.assertEqual(functions, ["bar"])
        self.assertFalse(provider.is_changed)
        self.file_observer.watch.assert_not_called()

    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_does_not_reload_incase_if_change_flag_is_false_and_get_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock
    ):
        FileObserverMock.return_value = self.file_observer

        func = Mock()
        extract_result = {"foo": func}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )

        self.file_observer.watch.reset_mock()
        self.assertEqual(provider.get("foo"), func)
        self.assertIsNone(provider.get("foo2"))
        self.assertFalse(provider.is_changed)
        self.file_observer.watch.assert_not_called()

    @patch("samcli.lib.providers.sam_function_provider.SamLocalStackProvider.get_stacks")
    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_does_not_reload_incase_if_change_flag_is_false_and_get_resources_by_stack_path_mathod_called(
        self, get_template_mock, extract_mock, FileObserverMock, get_stacks_mock
    ):
        FileObserverMock.return_value = self.file_observer

        func = Mock()
        extract_result = {"foo": func}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )

        self.file_observer.watch.reset_mock()
        self.assertEqual(provider.get_resources_by_stack_path("childStack"), {"a": "b"})
        with self.assertRaises(RuntimeError):
            provider.get_resources_by_stack_path("childStack/childStack2")
        self.assertFalse(provider.is_changed)
        self.file_observer.watch.assert_not_called()

    @patch("samcli.lib.providers.sam_function_provider.FileObserver")
    @patch.object(SamFunctionProvider, "_extract_functions")
    @patch("samcli.lib.providers.provider.SamBaseProvider.get_template")
    def test_provider_stop_will_stop_all_observers(self, get_template_mock, extract_mock, FileObserverMock):
        FileObserverMock.return_value = self.file_observer

        extract_result = {"foo": "bar"}
        extract_mock.return_value = extract_result

        template = {"Resources": {"a": "b"}}
        template2 = {"Resources": {"a": "b"}}
        get_template_mock.return_value = template
        stack = make_root_stack(template, self.parameter_overrides)
        stack2 = Stack("", "childStack", "child/template.yaml", self.parameter_overrides, template2)
        provider = RefreshableSamFunctionProvider(
            [stack, stack2], self.parameter_overrides, self.global_parameter_overrides
        )
        provider.stop_observer()

        self.file_observer.stop.assert_called_once()
