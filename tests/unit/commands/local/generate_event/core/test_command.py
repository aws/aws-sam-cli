import unittest
from unittest.mock import Mock, patch

from samcli.commands.local.generate_event.core.command import CoreGenerateEventCommand
from samcli.commands.local.generate_event.cli import DESCRIPTION
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestLocalGenerateEventCommand(unittest.TestCase):
    @patch.object(CoreGenerateEventCommand, "get_params")
    def test_get_options_local_invoke_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam local generate-event"
        ctx.parent.command_path = "sam"
        formatter = MockFormatter(scrub_text=True)

        cmd = CoreGenerateEventCommand(name="local generate-event", requires_credentials=False, description=DESCRIPTION)
        expected_output = {
            "Commands": [
                ("alexa-skills-kit", ""),
                ("alexa-smart-home", ""),
                ("alb", ""),
                ("apigateway", ""),
                ("appsync", ""),
                ("batch", ""),
                ("cloudformation", ""),
                ("cloudfront", ""),
                ("codecommit", ""),
                ("codepipeline", ""),
                ("cognito", ""),
                ("config", ""),
                ("connect", ""),
                ("dynamodb", ""),
                ("cloudwatch", ""),
                ("kinesis", ""),
                ("lex", ""),
                ("lex-v2", ""),
                ("rekognition", ""),
                ("s3", ""),
                ("sagemaker", ""),
                ("ses", ""),
                ("sns", ""),
                ("sqs", ""),
                ("stepfunctions", ""),
                ("workmail", ""),
            ],
            "Customize event by adding parameter flags.": [
                ("", ""),
                ("$sam local generate-event s3 " "[put/delete] --help\x1b[0m", ""),
                ("$sam local generate-event s3 " "[put/delete] --bucket " "<bucket> --key <key>\x1b[0m", ""),
            ],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Generate event S3 sends to local Lambda function": [
                ("", ""),
                ("$sam local " "generate-event s3 " "[put/delete]\x1b[0m", ""),
            ],
            "Test generated event with serverless function locally!": [
                ("", ""),
                (
                    "$sam local "
                    "generate-event "
                    "s3 [put/delete] "
                    "--bucket "
                    "<bucket> --key "
                    "<key> | sam "
                    "invoke -e "
                    "-\x1b[0m",
                    "",
                ),
            ],
        }
        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
