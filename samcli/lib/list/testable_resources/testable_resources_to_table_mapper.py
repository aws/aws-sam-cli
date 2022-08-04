"""
Implementation of the testable resources to table mapper
"""
from typing import Dict, Any
from collections import OrderedDict
from samcli.lib.list.list_interfaces import Mapper


class TestableResourcesToTableMapper(Mapper):
    def map(self, data: list) -> Dict[Any, Any]:
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
                    "Cloud Endpoint/FURL": "Cloud Endpoint/FURL",
                    "Methods": "Methods",
                }
            ),
            "table_name": "Testable Resources",
            "data": entry_list,
        }
        return table_data
