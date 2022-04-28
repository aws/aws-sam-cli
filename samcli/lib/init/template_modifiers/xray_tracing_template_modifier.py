"""
Class used to parse and update template when tracing is enabled
"""
import logging
from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier

LOG = logging.getLogger(__name__)


class XRayTracingTemplateModifier(TemplateModifier):

    FIELD_NAME = "Tracing"
    GLOBALS = "Globals:\n"
    RESOURCE = "Resources:\n"
    FUNCTION = "  Function:\n"
    TRACING = "    Tracing: Active\n"
    COMMENT = (
        "# More info about Globals: "
        "https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n"
    )

    def _add_new_field_to_template(self):
        """
        Add new field to SAM template
        """
        global_section_position = self._section_position(self.GLOBALS)

        if global_section_position >= 0:
            function_section_position = self._section_position(self.FUNCTION, global_section_position)

            if function_section_position >= 0:
                field_positon = self._field_position(function_section_position, self.FIELD_NAME)
                if field_positon >= 0:
                    self.template[field_positon] = self.TRACING
                    return

                new_fields = [self.TRACING]
                _section_position = function_section_position

            else:
                new_fields = [self.FUNCTION, self.TRACING]
                _section_position = global_section_position + 1

            self.template = self._add_fields_to_section(_section_position, new_fields)

        else:
            resource_section_position = self._section_position(self.RESOURCE)
            globals_section_data = [
                self.COMMENT,
                self.GLOBALS,
                self.FUNCTION,
                self.TRACING,
                "\n",
            ]
            self.template = (
                self.template[:resource_section_position]
                + globals_section_data
                + self.template[resource_section_position:]
            )

    def _print_sanity_check_error(self):
        link = (
            "https://docs.aws.amazon.com/serverless-application-model/latest"
            "/developerguide/sam-resource-function.html#sam-function-tracing"
        )
        message = f"Warning: Unable to add Tracing to the project. To learn more about Tracing visit {link}"
        LOG.warning(message)
