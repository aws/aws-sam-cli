"""
Class used to parse and update template with new field
"""
import logging
from abc import abstractmethod
from copy import deepcopy
from typing import Any, List
from yaml.parser import ParserError
from samcli.yamlhelper import parse_yaml_file


LOG = logging.getLogger(__name__)


class TemplateModifier:
    def __init__(self, location):
        self.template_location = location
        self.template = self._get_template()
        self.copy_of_original_template = deepcopy(self.template)

    def modify_template(self):
        """
        This method modifies the template by first added the new field to the template
        and then run a sanity check on the template to know if the template matches the
        CFN yaml
        """
        self._add_new_field_to_template()
        self._write(self.template)
        if not self._sanity_check():
            self._write(self.copy_of_original_template)

    @abstractmethod
    def _add_new_field_to_template(self):
        pass

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

    def _add_fields_to_section(self, position: int, fields: List[str]) -> Any:
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
        section_space_count = self.template[position].find(self.template[position].strip())
        start_position = position + 1
        template = self.template[start_position:]
        for index, line in enumerate(template):
            if not (line.find(line.strip()) > section_space_count or line.startswith("#")):
                return self.template[: start_position + index] + fields + self.template[start_position + index :]
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
            self._print_sanity_check_error()
            return False

    @abstractmethod
    def _print_sanity_check_error(self):
        pass

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
