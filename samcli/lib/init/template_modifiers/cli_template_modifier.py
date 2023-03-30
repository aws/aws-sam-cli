"""
Class used to parse and update template with new field
"""
import logging
from abc import abstractmethod
from copy import deepcopy

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
        self._update_template_fields()
        self._write(self.template)
        if not self._sanity_check():
            self._write(self.copy_of_original_template)

    @abstractmethod
    def _update_template_fields(self):
        pass

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

    @abstractmethod
    def _write(self, template: list):
        pass

    @abstractmethod
    def _get_template(self):
        pass
