"""
A center hub for checker logic
"""
import os
import functools
import logging
from typing import Any

import click

#!!! REMOVE import click AND PUT FUNCtion that uses it into save_data file

from boto3.session import Session

from samtranslator.translator.translator import Translator
from samtranslator.public.exceptions import InvalidDocumentException
from samtranslator.parser import parser

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
from samcli.commands.check.bottle_necks import BottleNecks

from samcli.commands.check.print_results import CheckResults

from samcli.yamlhelper import yaml_parse

from samcli.lib.replace_uri.replace_uri import replace_local_codeuri
from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from ..exceptions import InvalidSamDocumentException

from samcli.commands.check.lib.load_data import LoadData
from samcli.commands.check.bottle_neck_calculations import BottleNeckCalculations
from samcli.commands.check.pricing_calculations import PricingCalculations
from samcli.commands.check.lib.save_data import SaveGraphData
from samcli.commands.check.print_results import CheckResults
from samcli.commands.check.lib.resource_provider import ResourceProvider
from samcli.commands.check.graph_context import GraphContext


LOG = logging.getLogger(__name__)


class CheckContext:
    """
    This class translates a template (SAM or CFN json) into a CFN yaml format. Evenchually
    this class will also contain the major function calls for sam check, such as
    "ask_bottle_neck_quesions", "calculate_bottle_necks", "calculate_pricing", and
    "print_results"
    """

    _region: str
    _profile: str
    _template_path: str

    def __init__(self, region: str, profile: str, template_path: str):
        """
        Parameters
        ----------
            region: str
                Users region
            profile: str
                Users profile
            template_path: str
                Path of the template
        """
        self._region = region
        self._profile = profile
        self._template_path = template_path

    def run(self, config_file, load) -> None:
        """
        All main functions (bottle neck questions, pricing questions, calculations, print results)
        will be called here
        """

        if load:
            load_data = LoadData()
            graph = load_data.generate_graph_from_toml(config_file)

            bottle_neck_calculations = BottleNeckCalculations(graph)
            bottle_neck_calculations.run_calculations()

            pricing_calculations = PricingCalculations(graph)
            pricing_calculations.run_calculations()

            save_data = False

            if save_data:
                save_graph_data = SaveGraphData(graph)
                save_graph_data.save_to_config_file(config_file)

            results = CheckResults(graph, pricing_calculations.get_lambda_pricing_results())
            results.print_all_pricing_results()
            results.print_bottle_neck_results()

            return

        converted_template = self._transform_template()

        LOG.info("... analyzing application template")

        graph = _parse_template(converted_template)

        bottle_necks = BottleNecks(graph)
        bottle_necks.ask_entry_point_question()

        bottle_neck_calculations = BottleNeckCalculations(graph)
        bottle_neck_calculations.run_calculations()

        pricing_calculations = PricingCalculations(graph)
        pricing_calculations.run_calculations()

        save_data = ask_to_save_data()

        if save_data:
            save_graph_data = SaveGraphData(graph)
            save_graph_data.save_to_config_file(config_file)

        results = CheckResults(graph, pricing_calculations.get_lambda_pricing_results())
        results.print_all_pricing_results()
        results.print_bottle_neck_results()

    def _transform_template(self) -> Any:
        """
        Takes a sam template or a CFN json template and converts it into a CFN yaml template
        """
        wrapper = SamTranslatorWrapper({})
        managed_policy_map = wrapper.managed_policy_map()

        original_template = self._read_sam_file()

        updated_template = replace_local_codeuri(original_template)

        sam_translator = Translator(
            managed_policy_map=managed_policy_map,
            sam_parser=parser.Parser(),
            plugins=[],
            boto_session=Session(profile_name=self._profile, region_name=self._region),
        )

        # Translate template
        try:
            converted_template = sam_translator.translate(sam_template=updated_template, parameter_values={})
        except InvalidDocumentException as e:
            raise InvalidSamDocumentException(
                functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
            ) from e

        return converted_template

    def _read_sam_file(self) -> Any:
        """
        Reads the file (json and yaml supported) provided and returns the dictionary representation of the file.
        The file will be a sam application template file in SAM yaml, CFN json, or CFN yaml format

        Returns
        -------
            dict
                Dictionary representing the SAM Template

        Raises
        ------
            SamTemplateNotFoundException
                Raises this when the template file does not exist
        """

        if not os.path.exists(self._template_path):
            LOG.error("SAM Template Not Found")
            raise SamTemplateNotFoundException("Template at {} is not found".format(self._template_path))

        with open(self._template_path, "r", encoding="utf-8") as sam_template:
            sam_template = yaml_parse(sam_template.read())

        return sam_template


def _parse_template(template):

    all_resources = {}

    resource_provider = ResourceProvider(template)
    all_resources = resource_provider.get_all_resources()

    # After all resources have been parsed from template, pass them into the graph
    graph_context = GraphContext(all_resources)

    return graph_context.generate()


def ask_to_save_data():
    correct_input = False
    while not correct_input:
        user_input = click.prompt("Would you like to save this data in the samconfig file for future use? [y/n]")
        user_input = user_input.lower()

        if user_input == "y":
            return True
        elif user_input == "n":
            return False
        else:
            click.echo("Please enter a valid responce.")
