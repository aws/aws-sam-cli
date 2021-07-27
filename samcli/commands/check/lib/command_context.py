"""
A center hub for checker logic
"""
import os
import functools
import logging
from typing import Any

from boto3.session import Session

from samtranslator.translator.translator import Translator
from samtranslator.public.exceptions import InvalidDocumentException
from samtranslator.parser import parser

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
from samcli.commands.check.bottle_necks import BottleNecks
from samcli.commands.check.resources.LambdaFunction import LambdaFunction
from samcli.commands.check.resources.Graph import Graph
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION
from samcli.commands.check.calculations import Calculations
from samcli.commands.check.print_results import PrintResults


from samcli.yamlhelper import yaml_parse

from samcli.lib.replace_uri.replace_uri import replace_local_codeuri
from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.commands._utils.resources import AWS_LAMBDA_FUNCTION
from ..exceptions import InvalidSamDocumentException


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
        Args:
            region (str): Users region
            profile (str): Users profile
            template_path (str): [description]
        """
        self._region = region
        self._profile = profile
        self._template_path = template_path


    def run(self) -> None:
        """
        All main functions (bottle neck questions, pricing questions, calculations, print results)
        will be called here
        """
        self.transform_template()

    def run(self):
        self._transform_template()


        LOG.info("... analyzing application template")

        graph = _parse_template()

        bottle_necks = BottleNecks(graph)
        bottle_necks.ask_entry_point_question()

        calculations = Calculations(graph)
        calculations.run_bottle_neck_calculations()

        results = PrintResults(graph)
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

        :return dict: Dictionary representing the SAM Template
        :raises: SamTemplateNotFoundException when the template file does not exist
        """

        if not os.path.exists(self._template_path):
            LOG.error("SAM Template Not Found")
            raise SamTemplateNotFoundException("Template at {} is not found".format(self._template_path))

        with open(self._template_path, "r", encoding="utf-8") as sam_template:
            sam_template = yaml_parse(sam_template.read())

        return sam_template



def parse_template() -> Graph:
    """Parses the tenplate to retrieve resources

    Returns:
        Graph: Returns the generated graph object

def _parse_template() -> Graph:

    all_lambda_functions = []

    # template path
    # To-Do: allow user to set the path for the template
    path = os.path.realpath("template.yaml")

    # Get all lambda functions
    local_stacks = SamLocalStackProvider.get_stacks(path)[0]
    function_provider = SamFunctionProvider(local_stacks)
    functions = function_provider.get_all()  # List of all functions in the stacks
    for stack_function in functions:
        new_lambda_function = LambdaFunction(stack_function, AWS_LAMBDA_FUNCTION)
        all_lambda_functions.append(new_lambda_function)

    # After all resources have been parsed from template, pass them into the graph
    graph = Graph()
    graph.generate(all_lambda_functions)

    return graph
