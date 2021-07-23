"""
Library for Validating Sam Templates
"""
import logging
import functools

from samtranslator.public.exceptions import InvalidDocumentException
from samtranslator.parser import parser
from samtranslator.translator.translator import Translator
from boto3.session import Session

from samcli.lib.replace_uri.replace_uri import replace_local_codeuri as external_replace_local_codeuri
from samcli.lib.replace_uri.replace_uri import is_s3_uri as external_is_s3_uri

from samcli.yamlhelper import yaml_dump
from .exceptions import InvalidSamDocumentException

LOG = logging.getLogger(__name__)


class SamTemplateValidator:
    def __init__(self, sam_template, managed_policy_loader, profile=None, region=None):
        """
        Construct a SamTemplateValidator
        Design Details:
        managed_policy_loader is injected into the `__init__` to allow future expansion
        and overriding capabilities. A typically pattern is to pass the name of the class into
        the `__init__` as keyword args. As long as the class 'conforms' to the same 'interface'.
        This allows the class to be changed by the client and allowing customization of the class being
        initialized. Something I had in mind would be allowing a template to be run and checked
        'offline' (not needing aws creds). To make this an easier transition in the future, we ingest
        the ManagedPolicyLoader class.
        Parameters
        ----------
        sam_template dict
            Dictionary representing a SAM Template
        managed_policy_loader ManagedPolicyLoader
            Sam ManagedPolicyLoader
        """
        self.sam_template = sam_template
        self.managed_policy_loader = managed_policy_loader
        self.sam_parser = parser.Parser()
        self.boto3_session = Session(profile_name=profile, region_name=region)

    def is_valid(self):
        """
        Runs the SAM Translator to determine if the template provided is valid. This is similar to running a
        ChangeSet in CloudFormation for a SAM Template
        Raises
        -------
        InvalidSamDocumentException
             If the template is not valid, an InvalidSamDocumentException is raised
        """
        managed_policy_map = self.managed_policy_loader.load()

        sam_translator = Translator(
            managed_policy_map=managed_policy_map,
            sam_parser=self.sam_parser,
            plugins=[],
            boto_session=self.boto3_session,
        )

        self.sam_template = self._replace_local_codeuri()

        try:
            template = sam_translator.translate(sam_template=self.sam_template, parameter_values={})
            LOG.debug("Translated template is:\n%s", yaml_dump(template))
        except InvalidDocumentException as e:
            raise InvalidSamDocumentException(
                functools.reduce(lambda message, error: message + " " + str(error), e.causes, str(e))
            ) from e

    def _replace_local_codeuri(self):
        return external_replace_local_codeuri(self.sam_template)

    @staticmethod
    def is_s3_uri(uri):
        """
        Checks the uri and determines if it is a valid S3 Uri
        Parameters
        ----------
        uri str, required
            Uri to check
        Returns
        -------
        bool
            Returns True if the uri given is an S3 uri, otherwise False
        """
        return external_is_s3_uri(uri)

    @staticmethod
    def _update_to_s3_uri(property_key, resource_property_dict, s3_uri_value="s3://bucket/value"):
        """
        Updates the 'property_key' in the 'resource_property_dict' to the value of 's3_uri_value'
        Note: The function will mutate the resource_property_dict that is pass in
        Parameters
        ----------
        property_key str, required
            Key in the resource_property_dict
        resource_property_dict dict, required
            Property dictionary of a Resource in the template to replace
        s3_uri_value str, optional
            Value to update the value of the property_key to
        """
        uri_property = resource_property_dict.get(property_key, ".")

        # ignore if dict or already an S3 Uri
        if isinstance(uri_property, dict) or external_is_s3_uri(uri_property):
            return

        resource_property_dict[property_key] = s3_uri_value