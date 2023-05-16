"""
Wrapper for the SAM Translator and Parser classes.

##### NOTE #####
This module uses internal packages of SAM Translator library in order to provide a nice interface for the CLI. This is
a tech debt that we have decided to take on. This will be eventually thrown away when SAM Translator exposes a
rich public interface.
"""

import copy
import functools
from typing import Dict

from samtranslator.model import ResourceTypeResolver, sam_resources

# SAM Translator Library Internal module imports #
from samtranslator.model.exceptions import (
    InvalidDocumentException,
    InvalidEventException,
    InvalidResourceException,
    InvalidTemplateException,
)
from samtranslator.plugins import LifeCycleEvents
from samtranslator.sdk.resource import SamResource, SamResourceType
from samtranslator.translator.translator import prepare_plugins
from samtranslator.validator.validator import SamTemplateValidator

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException

from .local_uri_plugin import SupportLocalUriPlugin


class SamTranslatorWrapper:
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

        # Temporarily disabling validation for DeletionPolicy and UpdateReplacePolicy when language extensions are set
        self._patch_language_extensions()

        try:
            parser.parse(template_copy, all_plugins)  # parse() will run all configured plugins
        except InvalidDocumentException as e:
            raise InvalidSamDocumentException(
                functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
            ) from e

        return template_copy

    @property
    def template(self):
        return copy.deepcopy(self._sam_template)

    def _patch_language_extensions(self) -> None:
        """
        Monkey patch SamResource.valid function to exclude checking DeletionPolicy
        and UpdateReplacePolicy when language extensions are set
        """
        template_copy = self.template
        if self._check_using_language_extension(template_copy):

            def patched_func(self):
                if self.condition:
                    if not isinstance(self.condition, str):
                        raise InvalidDocumentException(
                            [InvalidTemplateException("Every Condition member must be a string.")]
                        )
                return SamResourceType.has_value(self.type)

            SamResource.valid = patched_func

    @staticmethod
    def _check_using_language_extension(template: Dict) -> bool:
        """
        Check if language extensions are set in the template's Transform
        :param template: template to check
        :return: True if language extensions are set in the template, False otherwise
        """
        transform = template.get("Transform")
        if transform:
            if isinstance(transform, str) and transform.startswith("AWS::LanguageExtensions"):
                return True
            if isinstance(transform, list):
                for transform_instance in transform:
                    if not isinstance(transform_instance, str):
                        continue
                    if transform_instance.startswith("AWS::LanguageExtensions"):
                        return True
        return False


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

    @staticmethod
    def _validate(sam_template: Dict) -> None:
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
