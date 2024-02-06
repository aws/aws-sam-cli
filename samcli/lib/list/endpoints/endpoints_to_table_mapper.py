"""
Implementation of the endpoints to table mapper
"""

from collections import OrderedDict
from typing import Any, Dict

from samcli.lib.list.list_interfaces import Mapper

NO_DATA = "-"
SPACING = ""
CLOUD_ENDPOINT = "CloudEndpoint"
METHODS = "Methods"


class EndpointsToTableMapper(Mapper):
    """
    Mapper class for mapping endpoints data for table output
    """

    def map(self, data: list) -> Dict[Any, Any]:
        """
        Maps data to the format needed for consumption by the table consumer

        Parameters
        ----------
        data: list
            List of dictionaries containing the entries of the endpoints data

        Returns
        -------
        table_data: Dict[Any, Any]
            Dictionary containing the information and data needed for the table consumer
            to output the data in table format
        """
        entry_list = []

        # Parse through the data object and separate out each data point we want to display.
        # If the data is none, default to using a "-"
        for endpoint in data:
            cloud_endpoint_furl_string = endpoint.get(CLOUD_ENDPOINT, NO_DATA)
            methods_string = NO_DATA
            cloud_endpoint_furl_multi_list = []

            # Build row of cloud endpoint data
            if isinstance(endpoint.get(CLOUD_ENDPOINT, NO_DATA), list) and endpoint.get(CLOUD_ENDPOINT, []):
                cloud_endpoint_furl_string = endpoint.get(CLOUD_ENDPOINT, [NO_DATA])[0]
                if len(endpoint.get(CLOUD_ENDPOINT, [])) > 1:
                    cloud_endpoint_furl_multi_list = endpoint.get(CLOUD_ENDPOINT, [SPACING, SPACING])[1:]

            # Build row of methods data
            if isinstance(endpoint.get(METHODS, NO_DATA), list) and endpoint.get(METHODS, []):
                methods_string = "; ".join(endpoint.get(METHODS, []))

            # Generate the list of endpoint data to be displayed. Each row displays an element in list,
            # where each element is a list of the columns.
            entry_list.append(
                [
                    endpoint.get("LogicalResourceId", NO_DATA),
                    endpoint.get("PhysicalResourceId", NO_DATA),
                    cloud_endpoint_furl_string,
                    methods_string,
                ]
            )

            # Add a spacing column with the next endpoint in the table in case there are multiple endpoints to display.
            if cloud_endpoint_furl_multi_list:
                for url in cloud_endpoint_furl_multi_list:
                    entry_list.append([SPACING, SPACING, url, SPACING])

        # Build out the table with the data collected to represent the endpoints
        table_data = {
            "format_string": "{Resource ID:<{0}} {Physical ID:<{1}} {Cloud Endpoints:<{2}} {Methods:<{3}}",
            "format_args": OrderedDict(
                {
                    "Resource ID": "Resource ID",
                    "Physical ID": "Physical ID",
                    "Cloud Endpoints": "Cloud Endpoints",
                    "Methods": "Methods",
                }
            ),
            "table_name": "Endpoints",
            "data": entry_list,
        }
        return table_data
