"""
Implementation of the endpoints to table mapper
"""
from typing import Dict, Any
from collections import OrderedDict
from samcli.lib.list.list_interfaces import Mapper


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
        for endpoint in data:
            cloud_endpoint_furl_string = endpoint.get("CloudEndpoint", "-")
            methods_string = "-"
            cloud_endpoint_furl_multi_list = []
            if isinstance(endpoint.get("CloudEndpoint", "-"), list) and endpoint.get("CloudEndpoint", []):
                cloud_endpoint_furl_string = endpoint.get("CloudEndpoint", ["-"])[0]
                if len(endpoint.get("CloudEndpoint", [])) > 1:
                    cloud_endpoint_furl_multi_list = endpoint.get("CloudEndpoint", ["", ""])[1:]
            if isinstance(endpoint.get("Methods", "-"), list) and endpoint.get("Methods", []):
                methods_string = "; ".join(endpoint.get("Methods", []))

            entry_list.append(
                [
                    endpoint.get("LogicalResourceId", "-"),
                    endpoint.get("PhysicalResourceId", "-"),
                    cloud_endpoint_furl_string,
                    methods_string,
                ]
            )
            if cloud_endpoint_furl_multi_list:
                for url in cloud_endpoint_furl_multi_list:
                    entry_list.append(["", "", url, ""])
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
