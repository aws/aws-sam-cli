"""
Class used to parse and update template when tracing is enabled
"""
import logging
from typing import Any
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.main import round_trip_load as yaml_load, round_trip_dump as yaml_dump
from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier

LOG = logging.getLogger(__name__)


class ApplicationInsightsTemplateModifier(TemplateModifier):

    APPLICATION_INSIGHTS_NAME_PREFIX = "ApplicationInsights-SAM-"
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
    def _get_template(self) -> Any:
        with open(self.template_location) as file:
            return yaml_load(file)

    def _add_new_field_to_template(self):
        """
        Add new field to SAM template
        """
        self._add_app_insights_monitoring_section()

    def _add_app_insights_monitoring_section(self):
        resourceGroupName = self.APPLICATION_INSIGHTS_NAME_PREFIX + self.name
        resourceGroup = {
            self.TYPE_KEY: self.RESOURCE_GROUP_TYPE,
            self.PROPERTIES_KEY: {self.NAME_KEY: resourceGroupName,
                                  self.RESOURCE_QUERY_KEY: {self.TYPE_KEY: self.CFN_STACK_TYPE}},
        }

        appInsightsApplication = {
            self.TYPE_KEY: self.APPLICATION_INSIGHTS_TYPE,
            self.PROPERTIES_KEY: {self.RESOURCE_GROUP_NAME_KEY: resourceGroupName,
                                  self.AUTO_CONFIG_ENABLED_KEY: self.AUTO_CONFIG_VALUE},
            self.DEPENDS_ON_KEY: self.RESOURCE_GROUP_REF,
        }

        self.template[self.RESOURCES_KEY][self.RESOURCE_GROUP_REF] = CommentedMap(resourceGroup)
        self.template[self.RESOURCES_KEY][self.APPLICATION_INSIGHTS_REF] = CommentedMap(appInsightsApplication)

    def _print_sanity_check_error(self):
        link = (
            "https://docs.aws.amazon.com/serverless-application-model/latest"
            "/developerguide/sam-resource-function.html#sam-function-tracing"
        )
        message = f"""Warning: Unable to add Application Insights monitoring to the application.
        To learn more about Application Insights, visit {link}"""
        LOG.warning(message)

    def _write(self, template: list):
        """
        write generated template into SAM template

        Parameters
        ----------
        template : list
            array with updated template data
        """
        with open(self.template_location, "w") as file:
            yaml_dump(self.template, file)
