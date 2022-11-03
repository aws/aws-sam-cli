"""
Class used to parse and update template when application-insights is enabled
"""
import logging
from typing import Any
import ruamel.yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier

LOG = logging.getLogger(__name__)
yaml = YAML()
# set ignore aliases to true
class NonAliasingRTRepresenter(ruamel.yaml.representer.RoundTripRepresenter):
    def ignore_aliases(self, data):
        return True


class ApplicationInsightsTemplateModifier(TemplateModifier):

    TYPE_KEY = "Type"
    RESOURCES_KEY = "Resources"
    PROPERTIES_KEY = "Properties"
    NAME_KEY = "Name"
    RESOURCE_QUERY_KEY = "ResourceQuery"
    RESOURCE_GROUP_NAME_KEY = "ResourceGroupName"
    AUTO_CONFIG_ENABLED_KEY = "AutoConfigurationEnabled"
    DEPENDS_ON_KEY = "DependsOn"
    RESOURCE_GROUP_TYPE = "AWS::ResourceGroups::Group"
    CFN_STACK_TYPE = "CLOUDFORMATION_STACK_1_0"
    APPLICATION_INSIGHTS_TYPE = "AWS::ApplicationInsights::Application"
    RESOURCE_GROUP_REF = "ApplicationResourceGroup"
    APPLICATION_INSIGHTS_REF = "ApplicationInsightsMonitoring"
    AUTO_CONFIG_VALUE = "true"
    RESOURCE_GROUP_NAME = {"Fn::Join": ["", ["ApplicationInsights-SAM-", {"Ref": "AWS::StackName"}]]}

    def _get_template(self) -> Any:
        yaml.Representer = NonAliasingRTRepresenter
        with open(self.template_location) as file:
            return yaml.load(file)

    def _update_template_fields(self):
        """
        Add new resources to SAM template
        """
        self._add_app_insights_monitoring_section()

    def _add_app_insights_monitoring_section(self):
        resourceGroup = {
            self.TYPE_KEY: self.RESOURCE_GROUP_TYPE,
            self.PROPERTIES_KEY: {
                self.NAME_KEY: self.RESOURCE_GROUP_NAME,
                self.RESOURCE_QUERY_KEY: {self.TYPE_KEY: self.CFN_STACK_TYPE},
            },
        }

        appInsightsApplication = {
            self.TYPE_KEY: self.APPLICATION_INSIGHTS_TYPE,
            self.PROPERTIES_KEY: {
                self.RESOURCE_GROUP_NAME_KEY: self.RESOURCE_GROUP_NAME,
                self.AUTO_CONFIG_ENABLED_KEY: self.AUTO_CONFIG_VALUE,
            },
            self.DEPENDS_ON_KEY: self.RESOURCE_GROUP_REF,
        }

        self.template[self.RESOURCES_KEY][self.RESOURCE_GROUP_REF] = CommentedMap(resourceGroup)
        self.template[self.RESOURCES_KEY][self.APPLICATION_INSIGHTS_REF] = CommentedMap(appInsightsApplication)
        print("test")
        print(self.template)

    def _print_sanity_check_error(self):
        link = "https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch-application-insights.html"
        message = (
            f"Warning: Unable to add Application Insights monitoring to the application."
            f"\nTo learn more about Application Insights, visit {link}"
        )
        LOG.warning(message)

    def _write(self, template: list):
        """
        write generated template into SAM template

        Parameters
        ----------
        template : list
            array with updated template data
        """
        yaml.Representer = NonAliasingRTRepresenter
        print("test")
        print(self.template)
        with open(self.template_location, "w") as file:
            yaml.dump(self.template, file)
