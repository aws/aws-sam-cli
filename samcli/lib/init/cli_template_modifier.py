"""
Class to parse and update template when tracing is enabled
"""
import logging
from typing import Any, List
from yaml.parser import ParserError
from samcli.yamlhelper import parse_yaml_file


LOG = logging.getLogger(__name__)


class TemplateModifier:
    GLOBALS = "Globals:\n"
    RESOURCES = "Resources:\n"
    FUNCTION = "  Function:\n"
    TRACING = "    Tracing: Active\n"
    GLOBAL_COMMENT = (
        "# More info about Globals: "
        "https://github.com/awslabs/serverless-application-model/blob/master/docs/globals.rst\n"
    )

    def __init__(self, location):
        self.template_location = location
        self.template = self.get_template()
        self.copy_of_original_template = self.template

    def modify_template(self):
        """
        This method modifies the template by first added the new field to the template
        and then run a sanity check on the template to know if the template matches the
        CFN yaml
        """
        self.add_new_field_to_template()
        self.write(self.template)
        if not self.sanity_check():
            self.write(self.copy_of_original_template)

    def add_new_field_to_template(self):
        """
        Add new field to SAM template
        """

        global_section_position = self.section_position(self.GLOBALS)

        if global_section_position >= 0:
            function_section_position = self.section_position(self.FUNCTION, global_section_position)

            if function_section_position >= 0:
                field_positon = self.field_position(function_section_position, "Tracing")
                if field_positon >= 0:
                    self.template[field_positon] = self.TRACING
                    return

                new_fields = [self.TRACING]
                section_position = function_section_position

            else:
                new_fields = [self.FUNCTION, self.TRACING]
                section_position = global_section_position + 1

            self.template = self.add_fields_to_section(section_position, new_fields)

        else:
            resource_section_position = self.section_position(self.RESOURCES)
            global_section = [
                self.GLOBAL_COMMENT,
                self.GLOBALS,
                self.FUNCTION,
                self.TRACING,
                "\n",
            ]
            self.template = (
                self.template[:resource_section_position] + global_section + self.template[resource_section_position:]
            )

    def section_position(self, section: str, position: int = 0) -> int:
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

    def add_fields_to_section(self, position: int, fields: str) -> Any:
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

    def field_position(self, position: int, field: str) -> Any:
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

    def sanity_check(self) -> bool:
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

    def write(self, template: list):
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

    def get_template(self) -> List[str]:
        """
        Gets data the SAM templates and returns it in a array

        Returns
        -------
        list
            array with updated template data
        """
        with open(self.template_location, "r") as file:
            return file.readlines()
