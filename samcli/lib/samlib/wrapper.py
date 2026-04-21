"""
Wrapper for the SAM Translator and Parser classes.

##### NOTE #####
This module uses internal packages of SAM Translator library in order to provide a nice interface for the CLI. This is
a tech debt that we have decided to take on. This will be eventually thrown away when SAM Translator exposes a
rich public interface.
"""

import functools
import logging
from typing import Any, Dict, List

from samtranslator.model import ResourceTypeResolver, sam_resources
from samtranslator.model.exceptions import (
    InvalidDocumentException,
    InvalidEventException,
    InvalidResourceException,
    InvalidTemplateException,
)
from samtranslator.plugins import LifeCycleEvents
from samtranslator.translator.translator import prepare_plugins
from samtranslator.validator.validator import SamTemplateValidator

from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.cfn_language_extensions.models import (
    DynamicArtifactProperty,
)
from samcli.lib.cfn_language_extensions.utils import deep_thaw
from samcli.lib.samlib.local_uri_plugin import SupportLocalUriPlugin

LOG = logging.getLogger(__name__)


class SamTranslatorWrapper:
    def __init__(self, sam_template, parameter_values=None, offline_fallback=True, language_extension_result=None):
        """

        Parameters
        ----------
        sam_template dict:
            SAM Template dictionary
        parameter_values dict:
            SAM Template parameters (must contain psuedo and default parameters)
        offline_fallback bool:
            Set it to True to make the translator work entirely offline, if internet is not available
        language_extension_result : LanguageExtensionResult, optional
            Pre-computed result from expand_language_extensions(). When provided,
            original_template and dynamic_artifact_properties are taken from this
            result instead of being computed internally.
        """
        self.local_uri_plugin = SupportLocalUriPlugin()
        self.parameter_values = parameter_values
        self.extra_plugins = [
            # Extra plugin specific to the SAM CLI that will support local paths for CodeUri & DefinitionUri
            self.local_uri_plugin
        ]

        self._sam_template = sam_template
        self._offline_fallback = offline_fallback
        self._language_extension_result = language_extension_result

        if language_extension_result is not None:
            # Use pre-computed Phase 1 results
            self._original_template = language_extension_result.original_template
            self._dynamic_artifact_properties: List[DynamicArtifactProperty] = list(
                language_extension_result.dynamic_artifact_properties
            )
        else:
            # Preserve the original template with a deep copy for CloudFormation deployment
            # This ensures Fn::ForEach and other language extensions remain intact
            self._original_template = deep_thaw(sam_template)
            # Dynamic artifact properties detected in Fn::ForEach blocks
            # These will be handled via Mappings transformation during sam package
            self._dynamic_artifact_properties: List[DynamicArtifactProperty] = []

    def run_plugins(self, convert_local_uris=True):
        """
        Run SAM Translator plugins on the template (Phase 2 only).

        This method assumes it receives an already-expanded template — language
        extension expansion (Phase 1) should have been performed by the caller
        via expand_language_extensions() before constructing this wrapper.
        """
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

    @property
    def template(self):
        return deep_thaw(self._sam_template)

    def get_original_template(self) -> Dict[str, Any]:
        """
        Get the original unexpanded template for CloudFormation deployment.

        This method returns a deep copy of the original template that was passed
        to the constructor, preserving Fn::ForEach and other language extension
        constructs intact. This is used when the template needs to be sent to
        CloudFormation, which will process the AWS::LanguageExtensions transform
        server-side.

        Returns
        -------
        dict
            A deep copy of the original template with language extensions preserved
        """
        result: Dict[str, Any] = deep_thaw(self._original_template)
        return result

    def get_dynamic_artifact_properties(self) -> List[DynamicArtifactProperty]:
        """
        Get the list of dynamic artifact properties detected in Fn::ForEach blocks.

        This method returns the dynamic artifact properties that were detected
        during template processing. These properties use loop variables in their
        values (e.g., CodeUri: ./services/${Name}) and need to be handled via
        Mappings transformation during sam package.

        Returns
        -------
        List[DynamicArtifactProperty]
            List of dynamic artifact property locations
        """
        return self._dynamic_artifact_properties


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
