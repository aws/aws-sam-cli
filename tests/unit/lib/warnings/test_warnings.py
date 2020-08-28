from unittest import TestCase
from samcli.lib.warnings.sam_cli_warning import TemplateWarningsChecker, CodeDeployWarning
from samcli.yamlhelper import yaml_parse
from parameterized import parameterized, param
import os

FAULTY_TEMPLATE = """
Resources:
  Function:
    Type: AWS::Serverless::Function
    Properties:
      DeploymentPreference:
        Events: ''

  preTrafficHook:
    Type: AWS::Serverless::Function
    Properties:
      DeploymentPreference:
        Enabled: false
"""

ALL_DISABLED_TEMPLATE = """
Resources:
  Function:
    Type: AWS::Serverless::Function
    Properties:
      DeploymentPreference:
        Enabled: false

  preTrafficHook:
    Type: AWS::Serverless::Function
    Properties:
      DeploymentPreference:
        Enabled: false
"""

ALL_ENABLED_TEMPLATE = """
Resources:
  Function:
    Type: AWS::Serverless::Function
    Properties:
      DeploymentPreference:
        Event: 'some-event'

  preTrafficHook:
    Type: AWS::Serverless::Function
    Properties:
      DeploymentPreference:
        Event: 'some-event'
"""


class TestWarnings(TestCase):
    def setUp(self):
        self.msg = "message"
        os.environ["SAM_CLI_TELEMETRY"] = "0"

    @parameterized.expand(
        [
            param(FAULTY_TEMPLATE, CodeDeployWarning.WARNING_MESSAGE, True),
            param(ALL_DISABLED_TEMPLATE, CodeDeployWarning.WARNING_MESSAGE, False),
            param(ALL_ENABLED_TEMPLATE, CodeDeployWarning.WARNING_MESSAGE, False),
        ]
    )
    def test_warning_check(self, template_txt, expected_warning_msg, message_present):
        template_dict = yaml_parse(template_txt)
        current_warning_checker = TemplateWarningsChecker()
        actual_warning_msg = current_warning_checker.check_template_for_warning(
            CodeDeployWarning.__name__, template_dict
        )
        if not message_present:
            self.assertIsNone(actual_warning_msg)
        else:
            self.assertEqual(expected_warning_msg, actual_warning_msg)


class TestCodeDeployWarning(TestCase):
    def setUp(self):
        self.msg = "message"
        os.environ["SAM_CLI_TELEMETRY"] = "0"

    @parameterized.expand(
        [param(FAULTY_TEMPLATE, True), param(ALL_DISABLED_TEMPLATE, False), param(ALL_ENABLED_TEMPLATE, False)]
    )
    def test_code_deploy_warning(self, template, expected):
        code_deploy_warning = CodeDeployWarning()
        (is_warning, message) = code_deploy_warning.check(yaml_parse(template))
        self.assertEqual(expected, is_warning)
