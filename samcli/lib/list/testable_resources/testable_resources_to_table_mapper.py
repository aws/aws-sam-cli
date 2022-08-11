"""
Implementation of the testable resources to table mapper
"""
from typing import Dict, Any
from collections import OrderedDict
from samcli.lib.list.list_interfaces import Mapper


class TestableResourcesToTableMapper(Mapper):
    """
    Mapper class for mapping testable-resources data for table output
    """

    def map(self, data: list) -> Dict[Any, Any]:
        """
        Maps data to the format needed for consumption by the table consumer

        Parameters
        ----------
        data: list
            List of dictionaries containing the entries of the testable resources data

        Returns
        -------
        table_data: Dict[Any, Any]
            Dictionary containing the information and data needed for the table consumer
            to output the data in table format
        """
        entry_list = []
        for testable_resource in data:
            cloud_endpoint_furl_string = testable_resource.get("CloudEndpointOrFunctionURL", "-")
            methods_string = "-"
            cloud_endpoint_furl_multi_list = []
            if isinstance(testable_resource.get("CloudEndpointOrFunctionURL", "-"), list) and testable_resource.get(
                "CloudEndpointOrFunctionURL", []
            ):
                cloud_endpoint_furl_string = testable_resource.get("CloudEndpointOrFunctionURL", ["-"])[0]
                if len(testable_resource.get("CloudEndpointOrFunctionURL", [])) > 1:
                    cloud_endpoint_furl_multi_list = testable_resource.get("CloudEndpointOrFunctionURL", ["", ""])[1:]
            if isinstance(testable_resource.get("Methods", "-"), list) and testable_resource.get("Methods", []):
                methods_string = "; ".join(testable_resource.get("Methods", []))

            entry_list.append(
                [
                    testable_resource.get("LogicalResourceId", "-"),
                    testable_resource.get("PhysicalResourceId", "-"),
                    cloud_endpoint_furl_string,
                    methods_string,
                ]
            )
            if cloud_endpoint_furl_multi_list:
                for url in cloud_endpoint_furl_multi_list:
                    entry_list.append(["", "", url, ""])
        table_data = {
            "format_string": "{Resource ID:<{0}} {Physical ID:<{1}} {Cloud Endpoint/FURL:<{2}} {Methods:<{3}}",
            "format_args": OrderedDict(
                {
                    "Resource ID": "Resource ID",
                    "Physical ID": "Physical ID",
                    "Cloud Endpoint/FURL": "Cloud Endpoint/Function URL",
                    "Methods": "Methods",
                }
            ),
            "table_name": "Testable Resources",
            "data": entry_list,
        }
        return table_data
