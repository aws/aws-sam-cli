"""
Class used to parse and update template when structured logging is enabled
"""

import logging
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.representer import RoundTripRepresenter

from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier

LOG = logging.getLogger(__name__)


class StructuredLoggingTemplateModifier(TemplateModifier):
    GLOBALS = "Globals"
    RESOURCE = "Resources"
    FUNCTION = "Function"
    LOGGING_CONFIG = "LoggingConfig"
    JSON_LOGFORMAT = {"LogFormat": "JSON"}
    DOC_LINK = (
        "https://docs.aws.amazon.com/serverless-application-model/latest/"
        "developerguide/sam-resource-function.html#sam-function-loggingconfig"
    )

    COMMENT = (
        "More info about Globals: "
        "https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n"
    )

    MESSAGE = (
        "You can add LoggingConfig parameters such as the Logformat, "
        "Log Group, and SystemLogLevel or ApplicationLogLevel. "
        f"Learn more here {DOC_LINK}.\n"
    )

    # set ignore aliases to true. This configuration avoids usage yaml aliases which is not parsed by CloudFormation.
    class NonAliasingRTRepresenter(RoundTripRepresenter):
        def ignore_aliases(self, data):
            return True

    def __init__(self, location):
        self.yaml = YAML()
        self.yaml.Representer = StructuredLoggingTemplateModifier.NonAliasingRTRepresenter
        super().__init__(location)

    def _get_template(self) -> Any:
        with open(self.template_location) as file:
            return self.yaml.load(file)

    def _update_template_fields(self):
        """
        Add new field to SAM template
        """
        if self.template.get(self.GLOBALS):
            template_globals = self.template.get(self.GLOBALS)

            function_globals = template_globals.get(self.FUNCTION, {})
            if not function_globals:
                template_globals[self.FUNCTION] = {}
            template_globals[self.FUNCTION][self.LOGGING_CONFIG] = CommentedMap(self.JSON_LOGFORMAT)
            template_globals[self.FUNCTION].yaml_set_comment_before_after_key(
                self.LOGGING_CONFIG, before=self.MESSAGE, indent=4
            )

        else:
            self._add_logging_config_with_globals()

    def _add_logging_config_with_globals(self):
        """Adds Globals and LoggingConfig fields"""
        global_section = {
            self.FUNCTION: {self.LOGGING_CONFIG: self.JSON_LOGFORMAT},
        }

        self.template = CommentedMap(self.template)
        self.template[self.GLOBALS] = CommentedMap(global_section)
        self.template[self.GLOBALS].yaml_set_comment_before_after_key(self.LOGGING_CONFIG, before=self.MESSAGE)
        self.template.yaml_set_comment_before_after_key(self.GLOBALS, before=self.COMMENT)

    def _print_sanity_check_error(self):
        message = (
            "Warning: Unable to add LoggingConfig to the project. "
            "To learn more about LoggingConfig visit {self.DOC_LINK}"
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
        with open(self.template_location, "w") as file:
            self.yaml.dump(self.template, file)
