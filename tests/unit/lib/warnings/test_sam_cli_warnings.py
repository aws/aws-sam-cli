from unittest import TestCase
from samcli.lib.warnings.sam_cli_warning import TemplateWarningsChecker, CodeDeployWarning, CodeDeployConditionWarning
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

NO_PROPERTY_TEMPLATE = """
Resources:
  Function:
    Type: AWS::Serverless::Function

  preTrafficHook:
    Type: AWS::Serverless::Function
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

NO_DEPLOYMENT_PREFERENCES = """
Resources:
  Function:
    Type: AWS::Serverless::Function
    Properties:
        Random: Property

  preTrafficHook:
    Type: AWS::Serverless::Function
    Properties:
        Random: Property
"""

NO_TYPE_RESOURCE = """
Resources:
  Fn::Transform:
    Name: AWS::Include
    Parameters:
      Location: ./deploy/queries.yaml
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
            param(NO_DEPLOYMENT_PREFERENCES, CodeDeployWarning.WARNING_MESSAGE, False),
            param(None, CodeDeployWarning.WARNING_MESSAGE, False),
        ]
    )
    def test_warning_check(self, template_txt, expected_warning_msg, message_present):
        if template_txt:
            template_dict = yaml_parse(template_txt)
        else:
            template_dict = None
        current_warning_checker = TemplateWarningsChecker()
        actual_warning_msg = current_warning_checker.check_template_for_warning(
            CodeDeployWarning.__name__, template_dict
        )
        if not message_present:
            self.assertIsNone(actual_warning_msg)
        else:
            self.assertEqual(expected_warning_msg, actual_warning_msg)

    def test_warning_check_invalid_warning_name(self):
        template_dict = yaml_parse(ALL_ENABLED_TEMPLATE)
        current_warning_checker = TemplateWarningsChecker()
        actual_warning_msg = current_warning_checker.check_template_for_warning("SomeRandomName", template_dict)
        self.assertIsNone(actual_warning_msg)


class TestCodeDeployWarning(TestCase):
    def setUp(self):
        self.msg = "message"
        os.environ["SAM_CLI_TELEMETRY"] = "0"

    @parameterized.expand(
        [
            param(FAULTY_TEMPLATE, True),
            param(ALL_DISABLED_TEMPLATE, False),
            param(ALL_ENABLED_TEMPLATE, False),
            param(NO_PROPERTY_TEMPLATE, False),
            param(NO_TYPE_RESOURCE, False),
        ]
    )
    def test_code_deploy_warning(self, template, expected):
        code_deploy_warning = CodeDeployWarning()
        (is_warning, message) = code_deploy_warning.check(yaml_parse(template))
        self.assertEqual(expected, is_warning)


FUNCTION_WITH_CONDITION = """
Resources:
  TestFunction:
    Condition: value_dont_matter
    Type: 'AWS::Serverless::Function'
    Properties:
      DeploymentPreference:
        Type: Linear10PercentEvery2Minutes
"""

FUNCTION_WITHOUT_CONDITOIN = """
Resources:
  TestFunction:
    Type: 'AWS::Serverless::Function'
    Properties:
      DeploymentPreference:
        Type: Linear10PercentEvery2Minutes
"""

FUNCTION_WITH_CONDITION_NO_DEPLOYMENT_PREFERENCES = """
Resources:
  TestFunction:
    Condition: value_dont_matter
    Type: 'AWS::Serverless::Function'
    Properties:
      Handler: index.handler
"""


class TestCodeDeployWarningCondition(TestCase):
    def setUp(self):
        self.msg = "message"
        os.environ["SAM_CLI_TELEMETRY"] = "0"

    @parameterized.expand(
        [
            param(FUNCTION_WITH_CONDITION, True),
            param(FUNCTION_WITHOUT_CONDITOIN, False),
            param(FUNCTION_WITH_CONDITION_NO_DEPLOYMENT_PREFERENCES, False),
        ]
    )
    def test_code_deploy_warning_condition(self, template, expected):
        code_deploy_warning_condition = CodeDeployConditionWarning()
        (is_warning, _) = code_deploy_warning_condition.check(yaml_parse(template))
        self.assertEqual(expected, is_warning)
