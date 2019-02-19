from unittest import TestCase
from parameterized import parameterized

from samcli.commands.local.lib.sam_function_code_provider import SamFunctionCodeProvider


class TestSamFunctionCodeProvider(TestCase):
    """
    Test all public methods with an input template
    """

    TEMPLATE = {
        "Resources": {

            "SamFunc1": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "/usr/foo/bar",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "SamFunc2": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": "s3://bucket/key",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "SamFunc3": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    # CodeUri is unsupported S3 location
                    "CodeUri": {
                        "Bucket": "bucket",
                        "Key": "key"
                    },
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "LambdaFunc1": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": {
                        "S3Bucket": "bucket",
                        "S3Key": "key"
                    },
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "LambdaFuncWithLocalPath": {
                "Type": "AWS::Lambda::Function",
                "Properties": {
                    "Code": "./some/path/to/code",
                    "Runtime": "nodejs4.3",
                    "Handler": "index.handler"
                }
            },
            "OtherResource": {
                "Type": "AWS::Serverless::Api",
                "Properties": {
                    "StageName": "prod",
                    "DefinitionUri": "s3://bucket/key"
                }
            }
        }
    }

    EXPECTED_FUNCTIONS = ["SamFunc1", "SamFunc2", "SamFunc3", "LambdaFunc1"]

    @parameterized.expand([
        ("SamFunc1", dict(
            name="SamFunc1",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri="/usr/foo/bar",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("SamFunc2", dict(
            name="SamFunc2",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("SamFunc3", dict(
            name="SamFunc3",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("LambdaFunc1", dict(
            name="LambdaFunc1",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri=".",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        )),
        ("LambdaFuncWithLocalPath", dict(
            name="LambdaFuncWithLocalPath",
            runtime="nodejs4.3",
            handler="index.handler",
            codeuri="./some/path/to/code",
            memory=None,
            timeout=None,
            environment=None,
            rolearn=None,
            layers=[]
        ))
    ])
    def test_every_function_type(self, name, expected_output):

        codeuri = SamFunctionCodeProvider(name, self.TEMPLATE, '')
        codeuri.__repr__()
        codeuri.__fspath__()

    def test__sanitize_inlinecode(self):
        SamFunctionCodeProvider._sanitize_inlinecode('')
        SamFunctionCodeProvider._extract_code_uri('', {}, SamFunctionCodeProvider._SERVERLESS_FUNCTION)

    def test_extract_code(self):
        SamFunctionCodeProvider.extract_code({}, '')
        SamFunctionCodeProvider.extract_codeuri('', {}, '')
