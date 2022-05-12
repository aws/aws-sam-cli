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
            self._add_tracing_section(
                global_section_position, self.FUNCTION, self.FIELD_NAME_FUNCTION_TRACING, self.TRACING_FUNCTION
            )
            self._add_tracing_section(global_section_position, self.API, self.FIELD_NAME_API_TRACING, self.TRACING_API)
        else:
            self._add_tracing_with_globals()

    def _add_tracing_with_globals(self):
        """Adds Globals and tracing fields"""
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
            self.template[:resource_section_position] + globals_section_data + self.template[resource_section_position:]
        )

    def _add_tracing_section(
        self,
        global_section_position: int,
        parent_section: str,
        tracing_field_name: str,
        tracing_field: str,
    ):
        """
        Adds tracing into the designated field

        Parameters
        ----------
        global_section_position : dict
            Position of the Globals field in the template
        parent_section: str
            Name of the parent section that the tracing field would be added.
        tracing_field_name: str
            Name of the tracing field, which will be used to check if it already exist
        tracing_field: str
            Name of the whole tracing field, which includes its name and value
        """
        parent_section_position = self._section_position(parent_section, global_section_position)
        if parent_section_position >= 0:
            field_positon_function = self._field_position(parent_section_position, tracing_field_name)
            if field_positon_function >= 0:
                self.template[field_positon_function] = tracing_field

            else:
                self.template = self._add_fields_to_section(parent_section_position, [tracing_field])
        else:
            self.template = self._add_fields_to_section(global_section_position, [parent_section, tracing_field])

    def _print_sanity_check_error(self):
        link = (
            "https://docs.aws.amazon.com/serverless-application-model/latest"
            "/developerguide/sam-resource-function.html#sam-function-tracing"
        )
        message = f"Warning: Unable to add Tracing to the project. To learn more about Tracing visit {link}"
        LOG.warning(message)
