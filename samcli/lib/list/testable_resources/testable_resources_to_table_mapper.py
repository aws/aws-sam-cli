"""
Implementation of the testable resources to table mapper
"""
from samcli.lib.list.list_interfaces import Mapper
from samcli.views.concrete_views.rich_table import RichTable


class TestableResourcesToTableMapper(Mapper):
    def map(self, data: list) -> RichTable:
        output = RichTable(title="Testable Resources", table_options={"show_lines": True})
        output.add_column("Resource ID", {"justify": "center", "no_wrap": True})
        output.add_column("Physical ID", {"justify": "center", "no_wrap": True})
        output.add_column("Cloud Endpoint/FURL", {"justify": "center", "no_wrap": True})
        output.add_column("Methods", {"justify": "center", "no_wrap": True})
        for testable_resource in data:
            cloud_endpoint_furl_string = testable_resource["CloudEndpointOrFURL"]
            methods_string = "-"
            if isinstance(testable_resource["CloudEndpointOrFURL"], list):
                cloud_endpoint_furl_string = "\n".join(testable_resource["CloudEndpointOrFURL"])
            if isinstance(testable_resource["Methods"], list) and testable_resource["Methods"]:
                methods_string = "; ".join(testable_resource["Methods"])
            output.add_row(
                [
                    testable_resource["LogicalResourceId"],
                    testable_resource["PhysicalResourceId"],
                    cloud_endpoint_furl_string,
                    methods_string,
                ]
            )
        return output
