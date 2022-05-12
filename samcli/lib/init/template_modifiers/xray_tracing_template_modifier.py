"""
Class used to parse and update template when tracing is enabled
"""
import logging
from samcli.lib.init.template_modifiers.cli_template_modifier import TemplateModifier

LOG = logging.getLogger(__name__)


class XRayTracingTemplateModifier(TemplateModifier):

    FIELD_NAME_FUNCTION_TRACING = "Tracing"
    FIELD_NAME_API_TRACING = "TracingEnabled"
    GLOBALS = "Globals:\n"
    RESOURCE = "Resources:\n"
    FUNCTION = "  Function:\n"
    TRACING_FUNCTION = "    Tracing: Active\n"
    API = "  Api:\n"
    TRACING_API = "    TracingEnabled: True\n"
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
            self._add_tracing_to_function(global_section_position)
            self._add_tracing_to_api(global_section_position)
        else:
            self._add_tracing_with_globals()

    def _add_tracing_with_globals(self):
        resource_section_position = self._section_position(self.RESOURCE)
        globals_section_data = [
            self.COMMENT,
            self.GLOBALS,
            self.FUNCTION,
            self.TRACING_FUNCTION,
            self.API,
            self.TRACING_API,
            "\n",
        ]
        self.template = (
                self.template[:resource_section_position]
                + globals_section_data
                + self.template[resource_section_position:]
        )

    def _add_tracing_to_api(self, global_section_position):
        """Adds TracingEnabled: True to the Globals -> Api section of the template"""
        api_section_position = self._section_position(self.API, global_section_position)
        if api_section_position >= 0:
            field_positon_api = self._field_position(api_section_position, self.FIELD_NAME_API_TRACING)
            if field_positon_api >= 0:
                self.template[field_positon_api] = self.TRACING_API

            else:
                self.template = self._add_fields_to_section(api_section_position, [self.TRACING_API])

        else:
            self.template = self._add_fields_to_section(global_section_position, [self.API, self.TRACING_API])

    def _add_tracing_to_function(self, global_section_position):
        """Adds Tracing:Active to the Globals -> Function section of the template"""
        function_section_position = self._section_position(self.FUNCTION, global_section_position)
        if function_section_position >= 0:
            field_positon_function = self._field_position(
                function_section_position, self.FIELD_NAME_FUNCTION_TRACING
            )
            if field_positon_function >= 0:
                self.template[field_positon_function] = self.TRACING_FUNCTION

            else:
                self.template = self._add_fields_to_section(function_section_position, [self.TRACING_FUNCTION])

        else:
            self.template = self._add_fields_to_section(
                global_section_position, [self.FUNCTION, self.TRACING_FUNCTION]
            )

    def _print_sanity_check_error(self):
        link = (
            "https://docs.aws.amazon.com/serverless-application-model/latest"
            "/developerguide/sam-resource-function.html#sam-function-tracing"
        )
        message = f"Warning: Unable to add Tracing to the project. To learn more about Tracing visit {link}"
        LOG.warning(message)
