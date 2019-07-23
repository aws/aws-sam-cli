"""
Class to store the API configurations in the SAM Template. This class helps store both implicit and explicit
APIs in a standardized format
"""

import logging
from collections import namedtuple

from six import string_types

LOG = logging.getLogger(__name__)


class ApiCollector(object):
    # Properties of each API. The structure is quite similar to the properties of AWS::Serverless::Api resource.
    # This is intentional because it allows us to easily extend this class to support future properties on the API.
    # We will store properties of Implicit APIs also in this format which converges the handling of implicit & explicit
    # APIs.
    Properties = namedtuple("Properties", ["apis", "binary_media_types", "cors", "stage_name", "stage_variables"])

    def __init__(self):
        # API properties stored per resource. Key is the LogicalId of the AWS::Serverless::Api resource and
        # value is the properties
        self.by_resource = {}

    def __iter__(self):
        """
        Iterator to iterate through all the APIs stored in the collector. In each iteration, this yields the
        LogicalId of the API resource and a list of APIs available in this resource.

        Yields
        -------
        str
            LogicalID of the AWS::Serverless::Api resource
        list samcli.commands.local.lib.provider.Api
            List of the API available in this resource along with additional configuration like binary media types.
        """

        for logical_id, _ in self.by_resource.items():
            yield logical_id, self._get_apis_with_config(logical_id)

    def add_apis(self, logical_id, apis):
        """
        Stores the given APIs tagged under the given logicalId

        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        apis : list of samcli.commands.local.lib.provider.Api
            List of APIs available in this resource
        """
        properties = self._get_properties(logical_id)
        properties.apis.extend(apis)

    def add_binary_media_types(self, logical_id, binary_media_types):
        """
        Stores the binary media type configuration for the API with given logical ID

        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        binary_media_types : list of str
            List of binary media types supported by this resource

        """
        properties = self._get_properties(logical_id)

        binary_media_types = binary_media_types or []
        for value in binary_media_types:
            normalized_value = self._normalize_binary_media_type(value)

            # If the value is not supported, then just skip it.
            if normalized_value:
                properties.binary_media_types.add(normalized_value)
            else:
                LOG.debug("Unsupported data type of binary media type value of resource '%s'", logical_id)

    def add_stage_name(self, logical_id, stage_name):
        """
        Stores the stage name for the API with the given local ID

        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        stage_name : str
            The stage_name string

        """
        properties = self._get_properties(logical_id)
        properties = properties._replace(stage_name=stage_name)
        self._set_properties(logical_id, properties)

    def add_stage_variables(self, logical_id, stage_variables):
        """
        Stores the stage variables for the API with the given local ID

        Parameters
        ----------
        logical_id : str
            LogicalId of the AWS::Serverless::Api resource

        stage_variables : dict
            A dictionary containing stage variables.

        """
        properties = self._get_properties(logical_id)
        properties = properties._replace(stage_variables=stage_variables)
        self._set_properties(logical_id, properties)

    def _get_apis_with_config(self, logical_id):
        """
        Returns the list of APIs in this resource along with other extra configuration such as binary media types,
        cors etc. Additional configuration is merged directly into the API data because these properties, although
        defined globally, actually apply to each API.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource to fetch data for

        Returns
        -------
        list of samcli.commands.local.lib.provider.Api
            List of APIs with additional configurations for the resource with given logicalId. If there are no APIs,
            then it returns an empty list
        """

        properties = self._get_properties(logical_id)

        # These configs need to be applied to each API
        binary_media = sorted(list(properties.binary_media_types))  # Also sort the list to keep the ordering stable
        cors = properties.cors
        stage_name = properties.stage_name
        stage_variables = properties.stage_variables

        result = []
        for api in properties.apis:
            # Create a copy of the API with updated configuration
            updated_api = api._replace(binary_media_types=binary_media,
                                       cors=cors,
                                       stage_name=stage_name,
                                       stage_variables=stage_variables)
            result.append(updated_api)

        return result

    def _get_properties(self, logical_id):
        """
        Returns the properties of resource with given logical ID. If a resource is not found, then it returns an
        empty data.

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource

        Returns
        -------
        samcli.commands.local.lib.sam_api_provider.ApiCollector.Properties
            Properties object for this resource.
        """

        if logical_id not in self.by_resource:
            self.by_resource[logical_id] = self.Properties(apis=[],
                                                           # Use a set() to be able to easily de-dupe
                                                           binary_media_types=set(),
                                                           cors=None,
                                                           stage_name=None,
                                                           stage_variables=None)

        return self.by_resource[logical_id]

    def _set_properties(self, logical_id, properties):
        """
        Sets the properties of resource with given logical ID. If a resource is not found, it does nothing

        Parameters
        ----------
        logical_id : str
            Logical ID of the resource
        properties : samcli.commands.local.lib.sam_api_provider.ApiCollector.Properties
             Properties object for this resource.
        """

        if logical_id in self.by_resource:
            self.by_resource[logical_id] = properties

    @staticmethod
    def _normalize_binary_media_type(value):
        """
        Converts binary media types values to the canonical format. Ex: image~1gif -> image/gif. If the value is not
        a string, then this method just returns None

        Parameters
        ----------
        value : str
            Value to be normalized

        Returns
        -------
        str or None
            Normalized value. If the input was not a string, then None is returned
        """

        if not isinstance(value, string_types):
            # It is possible that user specified a dict value for one of the binary media types. We just skip them
            return None

        return value.replace("~1", "/")
