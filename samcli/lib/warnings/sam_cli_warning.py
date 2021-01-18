"""
Provides all Warnings checkers for sam template
"""
import logging
from typing import Dict

LOG = logging.getLogger(__name__)


class TemplateWarning:
    """
    Top level class which all warnings should extend from.
    """

    def check(self, template_dict):  # pylint: disable=no-self-use
        raise Exception("NotImplementedException")


def _get_deployment_preferences_status(function):
    """
    Takes a AWS::Serverless::Function resource and checks if resource have a deployment preferences applied
    to it. If DeploymentPreference found then it returns its status if it is enabled or not.
    """
    deployment_preference = function.get("Properties", {}).get("DeploymentPreference", None)
    if not deployment_preference:
        # Missing deployment preferences treated as not enabled.
        return False
    return deployment_preference.get("Enabled", True)  # enabled by default


class TemplateWarningsChecker:
    def __init__(self):
        self.all_warnings = {
            CodeDeployWarning.__name__: CodeDeployWarning(),
            CodeDeployConditionWarning.__name__: CodeDeployConditionWarning(),
        }

    def check_template_for_warning(self, warning_name, template_dict):
        """
        Checks provided template against the warning based on warning_name.
        Parameters
        ----------
        warning_name: Name of warning which needs to be checked.
        template_dict: template dict

        Returns
        -------
        warning_message if warning detected. None if no warning found.
        """
        if not template_dict:
            return None
        warning = self.all_warnings.get(warning_name, None)
        if not warning:
            LOG.error("UnknownWarning name found: %s", warning_name)
            return None

        should_warn, warning_message = warning.check(template_dict)
        if should_warn:
            return warning_message
        return None


class CodeDeployWarning(TemplateWarning):
    WARNING_MESSAGE = """\
Your template includes a deployment configuration that will create an additional unecessary CodeDeploy Service Role.
By 9/25 the SAM service will no longer create this extra role, and any applications deployed after this date that 
directly reference this role will produce an error as the role will be removed. For more information on this issue 
and how to mitigate it, please read these docs[1]

[1] https://github.com/aws/aws-sam-cli/wiki/08-2020-codeploy-servicerole
    """

    def check(self, template_dict):
        """
        Checking if template dictionary have CodeDeployWarning or not.
        """
        functions = [
            resource
            for (_, resource) in template_dict.get("Resources", {}).items()
            if resource.get("Type", "") == "AWS::Serverless::Function"
        ]
        deployment_features_enabled_count = sum(
            1 for function in functions if _get_deployment_preferences_status(function)
        )
        deployment_features_disabled_count = sum(
            1 for function in functions if not _get_deployment_preferences_status(function)
        )

        send_warning = deployment_features_enabled_count > 0 and deployment_features_disabled_count > 0
        return (send_warning, self.WARNING_MESSAGE) if send_warning else (send_warning, "")


class CodeDeployConditionWarning(TemplateWarning):
    WARNING_MESSAGE = """\
Your template includes a deployment configuration with a Condition attached to it. SAM currently has a bug that
ignores conditions for DeploymentPreference, causing CodeDeploy DeploymentGroups to be created in error.
After October 23, 2020 the SAM service will fix this bug, causing subsequent deployments to remove these CodeDeploy 
DeploymentGroups if the attached Condition is false. For more information on this issue and how to mitigate it, 
please read these docs[1]

[1] https://github.com/aws/aws-sam-cli/wiki/08-2020-codeploy-deploymentgroup-condition
    """

    def check(self, template_dict):
        """
        Checking if template dictionary have Function with Condition and DeploymentPreferences which
        will trigger this warning.
        """
        functions = [
            resource
            for (_, resource) in template_dict.get("Resources", {}).items()
            if resource.get("Type", "") == "AWS::Serverless::Function"
        ]
        for function in functions:
            if self._have_condition(function) and self._have_deployment_preferences(function):
                return (True, self.WARNING_MESSAGE)
        return (False, "")

    @staticmethod
    def _have_condition(function: Dict) -> bool:
        condition = function.get("Condition", None)
        return condition is not None

    @staticmethod
    def _have_deployment_preferences(function: Dict) -> bool:
        deployment_preference = function.get("Properties", {}).get("DeploymentPreference", None)
        return deployment_preference is not None
