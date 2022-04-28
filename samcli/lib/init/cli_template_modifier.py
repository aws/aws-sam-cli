"""
Classes used to parse and update template when tracing is enabled
"""
import logging
from typing import Any, List
from yaml.parser import ParserError
from samcli.yamlhelper import parse_yaml_file


LOG = logging.getLogger(__name__)


class GlobalsSection:
    def __init__(self):
        self.globals = "Globals:\n"
        self.resource = "Resources:\n"
        self.function = "  Function:\n"
        self.tracing = "    Tracing: Active\n"
        self.comment = (
            "# More info about Globals: "
            "https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n"
        )

    def get_field(self, field: str):
        """
        Parameters
        ----------
        field : str
            Global field value

        Returns
        -------
        str
            field and it value
        """
        return self.tracing if field == "Tracing" else None


class TemplateModifier:
    def __init__(self, location):
        self.template_location = location
        self.template = self._get_template()
        self.copy_of_original_template = self.template

    def modify_template(self, field, globals_section):
        """
        This method modifies the template by first added the new field to the template
        and then run a sanity check on the template to know if the template matches the
        CFN yaml
        """
        self._add_new_field_to_template(field, globals_section)
        self._write(self.template)
        if not self._sanity_check():
            self._write(self.copy_of_original_template)

    def _add_new_field_to_template(self, field, globals_section):
        """
        Add new field to SAM template
        """

        field_and_value = globals_section.get_field(field)
        global_section_position = self._section_position(globals_section.globals)

        if global_section_position >= 0:
            function_section_position = self._section_position(globals_section.function, global_section_position)

            if function_section_position >= 0:
                field_positon = self._field_position(function_section_position, field)
                if field_positon >= 0:
                    self.template[field_positon] = field_and_value
                    return

                new_fields = [field_and_value]
                _section_position = function_section_position

            else:
                new_fields = [globals_section.function, field_and_value]
                _section_position = global_section_position + 1

            self.template = self._add_fields_to_section(_section_position, new_fields)

        else:
            resource_section_position = self._section_position(globals_section.resource)
            globals_section_data = [
                globals_section.comment,
                globals_section.globals,
                globals_section.function,
                field_and_value,
                "\n",
            ]
            self.template = (
                self.template[:resource_section_position]
                + globals_section_data
                + self.template[resource_section_position:]
            )

    def _section_position(self, section: str, position: int = 0) -> int:
        """
        validate if a section in the template exist

        Parameters
        ----------
        section : str
            A section in the SAM template
        position : int
            position to start searching for the section

        Returns
        -------
        int
            index of section in the template list
        """
        template = self.template[position:]
        for index, line in enumerate(template):
            if line.startswith(section):
                section_index = index + position if position else index
                return section_index
        return -1

    def _add_fields_to_section(self, position: int, fields: str) -> Any:
        """
        Adds fields to section in the template

        Parameters
        ----------
        position : int
            position to start searching for the section
        fields : str
            fields to be added to the SAM template

        Returns
        -------
        list
            array with updated template data
        """
        template = self.template[position:]
        for index, line in enumerate(template):
            if not (line.startswith(" ") or line.startswith("#")):
                return self.template[: position + index] + fields + self.template[position + index :]
        return self.template

    def _field_position(self, position: int, field: str) -> Any:
        """
        Checks if the field needed to be added to the SAM template already exist in the template

        Parameters
        ----------
        position : int
            section position to start the search
        field : str
            Field name

        Returns
        -------
        int
            index of the field if it exist else -1
        """
        template = self.template[position:]
        for index, line in enumerate(template):
            if field in line:
                return position + index
            if not (line.startswith(" ") or line.startswith("#")):
                break
        return -1

    def _sanity_check(self) -> bool:
        """
        Conducts sanity check on template using yaml parser to ensure the updated template meets
        CFN template criteria

        Returns
        -------
        bool
            True if templates passes sanity check else False
        """
        try:
            parse_template = parse_yaml_file(self.template_location)
            return bool(parse_template)
        except ParserError:
            link = (
                "https://docs.aws.amazon.com/serverless-application-model/latest"
                "/developerguide/sam-resource-function.html#sam-function-tracing"
            )
            message = f"Warning: Unable to add Tracing to the project. To learn more about Tracing visit {link}"
            LOG.warning(message)
            return False

    def _write(self, template: list):
        """
        write generated template into SAM template

        Parameters
        ----------
        template : list
            array with updated template data
        """
        with open(self.template_location, "w") as file:
            for line in template:
                file.write(line)

    def _get_template(self) -> List[str]:
        """
        Gets data the SAM templates and returns it in a array

        Returns
        -------
        list
            array with updated template data
        """
        with open(self.template_location, "r") as file:
            return file.readlines()
