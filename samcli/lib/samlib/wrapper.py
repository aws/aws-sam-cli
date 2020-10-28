"""
Wrapper for the SAM Translator and Parser classes.

##### NOTE #####
This module uses internal packages of SAM Translator library in order to provide a nice interface for the CLI. This is
a tech debt that we have decided to take on. This will be eventually thrown away when SAM Translator exposes a
rich public interface.
"""

import copy
import os
import json

import functools
import boto3

# SAM Translator Library Internal module imports #
from samtranslator.model.exceptions import (
    InvalidDocumentException,
    InvalidTemplateException,
    InvalidResourceException,
    InvalidEventException,
)
from samtranslator.validator.validator import SamTemplateValidator
from samtranslator.model import ResourceTypeResolver, sam_resources
from samtranslator.plugins import LifeCycleEvents
from samtranslator.translator.translator import prepare_plugins, Translator
from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
from samtranslator.parser.parser import Parser

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from .local_uri_plugin import SupportLocalUriPlugin


class SamTranslatorWrapper:

    _thisdir = os.path.dirname(os.path.abspath(__file__))
    _DEFAULT_MANAGED_POLICIES_FILE = os.path.join(_thisdir, "default_managed_policies.json")

    def __init__(self, sam_template, parameter_values=None, offline_fallback=True):
        """

        Parameters
        ----------
        sam_template dict:
            SAM Template dictionary
        parameter_values dict:
            SAM Template parameters (must contain psuedo and default parameters)
        offline_fallback bool:
            Set it to True to make the translator work entirely offline, if internet is not available
        """
        self.local_uri_plugin = SupportLocalUriPlugin()
        self.parameter_values = parameter_values
        self.extra_plugins = [
            # Extra plugin specific to the SAM CLI that will support local paths for CodeUri & DefinitionUri
            self.local_uri_plugin
        ]

        self._sam_template = sam_template
        self._offline_fallback = offline_fallback

    def run_plugins(self, convert_local_uris=True):
        template_copy = self.template

        additional_plugins = []
        if convert_local_uris:
            # Add all the plugins to convert local path if asked to.
            additional_plugins.append(self.local_uri_plugin)

        parser = _SamParserReimplemented()
        all_plugins = prepare_plugins(
            additional_plugins, parameters=self.parameter_values if self.parameter_values else {}
        )

        try:
            parser.parse(template_copy, all_plugins)  # parse() will run all configured plugins
        except InvalidDocumentException as e:
            raise InvalidSamDocumentException(
                functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
            ) from e

        return template_copy

    def __translate(self, parameter_values):
        """
        This method is unused and a Work In Progress
        """

        template_copy = self.template

        sam_parser = Parser()
        sam_translator = Translator(
            managed_policy_map=self.__managed_policy_map(),
            sam_parser=sam_parser,
            # Default plugins are already initialized within the Translator
            plugins=self.extra_plugins,
        )

        return sam_translator.translate(sam_template=template_copy, parameter_values=parameter_values)

    @property
    def template(self):
        return copy.deepcopy(self._sam_template)

    def __managed_policy_map(self):
        """
        This method is unused and a Work In Progress
        """
        try:
            iam_client = boto3.client("iam")
            return ManagedPolicyLoader(iam_client).load()
        except Exception as ex:

            if self._offline_fallback:
                # If offline flag is set, then fall back to the list of default managed policies
                # This should be sufficient for most cases
                with open(self._DEFAULT_MANAGED_POLICIES_FILE, "r") as fp:
                    return json.load(fp)

            # Offline is not enabled. So just raise the exception
            raise ex


class _SamParserReimplemented:
    """
    Re-implementation (almost copy) of Parser class from SAM Translator
    """

    def parse(self, sam_template, sam_plugins):
        self._validate(sam_template)
        sam_plugins.act(LifeCycleEvents.before_transform_template, sam_template)
        macro_resolver = ResourceTypeResolver(sam_resources)
        document_errors = []

        for logical_id, resource in sam_template["Resources"].items():
            try:
                if macro_resolver.can_resolve(resource):
                    macro_resolver.resolve_resource_type(resource).from_dict(
                        logical_id, resource, sam_plugins=sam_plugins
                    )
            except (InvalidResourceException, InvalidEventException) as e:
                document_errors.append(e)

        if document_errors:
            raise InvalidDocumentException(document_errors)

    def _validate(self, sam_template):
        """Validates the template and parameter values and raises exceptions if there's an issue

        :param dict sam_template: SAM template
        """

        if (
            "Resources" not in sam_template
            or not isinstance(sam_template["Resources"], dict)
            or not sam_template["Resources"]
        ):
            raise InvalidDocumentException([InvalidTemplateException("'Resources' section is required")])

        SamTemplateValidator.validate(sam_template)
