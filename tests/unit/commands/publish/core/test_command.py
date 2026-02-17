import unittest
from unittest.mock import Mock, patch
from samcli.commands.publish.core.command import PublishCommand
from tests.unit.cli.test_command import MockFormatter


class MockParams:
    def __init__(self, rv, name):
        self.rv = rv
        self.name = name

    def get_help_record(self, ctx):
        return self.rv


class TestPublishCommand(unittest.TestCase):
    @patch.object(PublishCommand, "get_params")
    def test_get_options_publish_command_text(self, mock_get_params):
        ctx = Mock()
        ctx.command_path = "sam publish"
        formatter = MockFormatter(scrub_text=True)
        # NOTE(sriram-mv): One option per option section.
        mock_get_params.return_value = [
            MockParams(rv=("--region", "Region"), name="region"),
            MockParams(rv=("--debug", ""), name="debug"),
            MockParams(rv=("--config-file", ""), name="config_file"),
            MockParams(rv=("--template-file", ""), name="template_file"),
            MockParams(rv=("--semantic-version", ""), name="semantic_version"),
        ]

        cmd = PublishCommand(
            name="publish",
            requires_credentials=True,
            description="Use this command to publish a packaged AWS SAM template to\n"
            "the AWS Serverless Application Repository to share within your team,\n"
            "across your organization, or with the community at large.\n\n"
            "This command expects the template's Metadata section to contain an\n"
            "AWS::ServerlessRepo::Application section with application metadata\n"
            "for publishing. For more details on this metadata section, see\n"
            "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-template-publishing-applications.html\n",
        )
        expected_output = {
            "AWS Credential Options": [("", ""), ("--region", "")],
            "Configuration Options": [
                ("", ""),
                ("Learn more about configuration files at:", ""),
                (
                    "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli"
                    "-config.html. ",
                    "",
                ),
                ("", ""),
                ("--config-file", ""),
            ],
            "Description": [(cmd.description + cmd.description_addendum, "")],
            "Examples": [],
            "Publish a packaged application": [
                ("", ""),
                ("$ sam publish -t packaged.yaml --region us-east-1\x1b[0m", ""),
            ],
            "Other Options": [("", ""), ("--debug", "")],
            "Publish Options": [("", ""), ("--template-file", ""), ("", ""), ("--semantic-version", "")],
        }

        cmd.format_options(ctx, formatter)
        self.assertEqual(formatter.data, expected_output)
