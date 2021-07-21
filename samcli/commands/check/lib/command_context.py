"""
A center hub for checker logic
"""
import os
import functools
import logging

import boto3
from boto3.session import Session

from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
from samtranslator.translator.translator import Translator
from samtranslator.public.exceptions import InvalidDocumentException
from samtranslator.parser import parser

from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException
from samcli.commands.check.bottle_necks import BottleNecks
from samcli.commands.check.graph_context import GraphContext
from samcli.commands.check.resources.LambdaFunction import LambdaFunction

from samcli.yamlhelper import yaml_parse

from samcli.lib.replace_uri.replace_uri import replace_local_codeuri
from samcli.lib.samlib.wrapper import SamTranslatorWrapper
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from ..exceptions import InvalidSamDocumentException


LOG = logging.getLogger(__name__)


class CheckContext:
    """
    This class translates a template (SAM or CFN json) into a CFN yaml format. Evenchually
    this class will also contain the major function calls for sam check, such as
    "ask_bottle_neck_quesions", "calculate_bottle_necks", "calculate_pricing", and
    "print_results"
    """

    def __init__(self, region, profile, template_path):
        self.region = region
        self.profile = profile
        self.template_path = template_path

    def run(self):
        self.transform_template()

        LOG.info("... analyzing application template")

        graph = self.parse_template()

        bottle_necks = BottleNecks(graph)
        bottle_necks.ask_entry_point_question()

    def parse_template(self):
        all_lambda_functions = []

        # template path
        path = os.path.realpath("template.yaml")

        # Get all lambda functions
        local_stacks = SamLocalStackProvider.get_stacks(path)[0]
        function_provider = SamFunctionProvider(local_stacks)
        functions = function_provider.get_all()  # List of all functions in the stacks
        for stack_function in functions:
            new_lambda_function = LambdaFunction(stack_function, "AWS::Lambda::Function")
            all_lambda_functions.append(new_lambda_function)

        # After all resources have been parsed from template, pass them into the graph
        graph_context = GraphContext(all_lambda_functions)

        return graph_context.generate()

    def transform_template(self):
        """
        Takes a sam template or a CFN json template and converts it into a CFN yaml template
        """
        wrapper = SamTranslatorWrapper({})
        managed_policy_map = wrapper.managed_policy_map()

        original_template = self.read_sam_file()

        updated_template = replace_local_codeuri(original_template)

        sam_translator = Translator(
            managed_policy_map=managed_policy_map,
            sam_parser=parser.Parser(),
            plugins=[],
            boto_session=Session(profile_name=self.profile, region_name=self.region),
        )

        # Translate template
        try:
            converted_template = sam_translator.translate(sam_template=updated_template, parameter_values={})
        except InvalidDocumentException as e:
            raise InvalidSamDocumentException(
                functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
            ) from e

        return converted_template

    def read_sam_file(self):
        """
        Reads the file (json and yaml supported) provided and returns the dictionary representation of the file.
        The file will be a sam application template file in SAM yaml, CFN json, or CFN yaml format

        :return dict: Dictionary representing the SAM Template
        :raises: SamTemplateNotFoundException when the template file does not exist
        """

        if not os.path.exists(self.template_path):
            LOG.error("SAM Template Not Found")
            raise SamTemplateNotFoundException("Template at {} is not found".format(self.template_path))

        with open(self.template_path, "r", encoding="utf-8") as sam_template:
            sam_template = yaml_parse(sam_template.read())

        return sam_template
