from unittest import TestCase
from unittest.mock import patch, ANY

from samcli.commands.init.interactive_event_bridge_flow import get_schema_template_details


class TestInteractiveEventBridge(TestCase):
    @patch("click.prompt")
    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_get_schema_template_details(self, schemas_api_caller, prompt_mock):
        prompt_mock.side_effect = ["1", "2"]
        schemas_api_caller.list_registries.return_value = {"registries": ["aws.events", "default"], "next_token": None}
        schemas_api_caller.list_schemas.return_value = {
            "schemas": [
                "aws.autoscaling.AWSAPICallViaCloudTrail",
                "aws.autoscaling.EC2InstanceLaunchSuccessful",
                "aws.autoscaling.EC2InstanceLaunchUnsuccessful",
                "aws.autoscaling.EC2InstanceTerminateLifecycleAction",
                "aws.autoscaling.EC2InstanceTerminateSuccessful",
                "aws.autoscaling.EC2InstanceTerminateUnsuccessful",
            ],
            "next_token": None,
        }
        schemas_api_caller.get_latest_schema_version.return_value = "1"
        schemas_api_caller.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "EC2InstanceLaunchSuccessful",
            "schemas_package_hierarchy": "schemas/aws/EC2InstanceLaunchSuccessful",
        }

        schema_template_details = get_schema_template_details(schemas_api_caller)
        self.assertEqual(schema_template_details["schema_full_name"], "aws.autoscaling.EC2InstanceLaunchSuccessful"),
        self.assertEqual(schema_template_details["schema_root_name"], "EC2InstanceLaunchSuccessful"),
        self.assertEqual(schema_template_details["registry_name"], "aws.events")
        self.assertEqual(schema_template_details["schema_version"], "1")
        self.assertEqual(schema_template_details["event_source"], "aws.autoscaling")
        self.assertEqual(schema_template_details["event_source_detail_type"], "aws.autoscaling response")
        self.assertEqual(
            schema_template_details["schemas_package_hierarchy"], "schemas/aws/EC2InstanceLaunchSuccessful"
        )
        prompt_mock.assert_any_call("Schema Registry", type=ANY, show_choices=False)
        prompt_mock.assert_any_call("Event Schemas", type=ANY, show_choices=False)

    @patch("click.prompt")
    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_registry_prompt_not_called_when_one_registry(self, schemas_api_caller, prompt_mock):
        prompt_mock.side_effect = ["2"]
        schemas_api_caller.list_registries.return_value = {"registries": ["aws.events"], "next_token": None}
        schemas_api_caller.list_schemas.return_value = {
            "schemas": [
                "aws.autoscaling.AWSAPICallViaCloudTrail",
                "aws.autoscaling.EC2InstanceLaunchSuccessful",
                "aws.autoscaling.EC2InstanceLaunchUnsuccessful",
                "aws.autoscaling.EC2InstanceTerminateLifecycleAction",
                "aws.autoscaling.EC2InstanceTerminateSuccessful",
                "aws.autoscaling.EC2InstanceTerminateUnsuccessful",
            ],
            "next_token": None,
        }
        schemas_api_caller.get_latest_schema_version.return_value = "1"
        schemas_api_caller.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "EC2InstanceLaunchSuccessful",
            "schemas_package_hierarchy": "schemas/aws/EC2InstanceLaunchSuccessful",
        }
        schema_template_details = get_schema_template_details(schemas_api_caller)
        self.assertEqual(schema_template_details["schema_full_name"], "aws.autoscaling.EC2InstanceLaunchSuccessful"),
        self.assertEqual(schema_template_details["schema_root_name"], "EC2InstanceLaunchSuccessful"),
        self.assertEqual(schema_template_details["registry_name"], "aws.events")
        self.assertEqual(schema_template_details["schema_version"], "1")
        self.assertEqual(schema_template_details["event_source"], "aws.autoscaling")
        self.assertEqual(schema_template_details["event_source_detail_type"], "aws.autoscaling response")
        self.assertEqual(
            schema_template_details["schemas_package_hierarchy"], "schemas/aws/EC2InstanceLaunchSuccessful"
        )
        prompt_mock.assert_called_once_with("Event Schemas", type=ANY, show_choices=False)

    @patch("click.prompt")
    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_schema_prompt_not_called_when_one_schema(self, schemas_api_caller, prompt_mock):
        prompt_mock.side_effect = ["1"]
        schemas_api_caller.list_registries.return_value = {"registries": ["aws.events"], "next_token": None}
        schemas_api_caller.list_schemas.return_value = {
            "schemas": ["aws.autoscaling.AWSAPICallViaCloudTrail"],
            "next_token": None,
        }
        schemas_api_caller.get_latest_schema_version.return_value = "1"
        schemas_api_caller.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "AWSAPICallViaCloudTrail",
            "schemas_package_hierarchy": "schemas/aws/AWSAPICallViaCloudTrail",
        }
        schema_template_details = get_schema_template_details(schemas_api_caller)
        self.assertEqual(schema_template_details["schema_full_name"], "aws.autoscaling.AWSAPICallViaCloudTrail"),
        self.assertEqual(schema_template_details["schema_root_name"], "AWSAPICallViaCloudTrail"),
        self.assertEqual(schema_template_details["registry_name"], "aws.events")
        self.assertEqual(schema_template_details["schema_version"], "1")
        self.assertEqual(schema_template_details["event_source"], "aws.autoscaling")
        self.assertEqual(schema_template_details["event_source_detail_type"], "aws.autoscaling response")
        self.assertEqual(schema_template_details["schemas_package_hierarchy"], "schemas/aws/AWSAPICallViaCloudTrail")
        self.assertFalse(prompt_mock.called)

    @patch("click.prompt")
    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_schema_prompt_paginate_with_next_page_choice(self, schemas_api_caller, prompt_mock):
        prompt_mock.side_effect = ["N", "N", "22", "N", "N", "25"]
        schemas_api_caller.list_registries.side_effect = [
            {
                "registries": [
                    "r1",
                    "r2",
                    "r3",
                    "r4",
                    "r5",
                    "r6",
                    "r7",
                    "r8",
                    "r9",
                    "r10",
                    "r11",
                    "r12",
                    "r13",
                    "r14",
                    "r15",
                    "r16",
                    "r17",
                    "r18",
                    "r19",
                    "r20",
                ],
                "next_token": "1234",
            },
            {"registries": ["r21", "r22", "r23", "r24", "r25", "r26", "r27", "r28", "r29", "r30"], "next_token": None},
        ]
        schemas_api_caller.list_schemas.side_effect = [
            {
                "schemas": [
                    "s1",
                    "s2",
                    "s3",
                    "s4",
                    "s5",
                    "s6",
                    "s7",
                    "s8",
                    "s9",
                    "s10",
                    "s11",
                    "s12",
                    "s13",
                    "s14",
                    "s15",
                    "s16",
                    "s17",
                    "s18",
                    "s19",
                    "s20",
                ],
                "next_token": "1234",
            },
            {"schemas": ["s21", "s22", "s23", "s24", "s25", "s26", "s27", "s28", "s29", "s30"], "next_token": None},
        ]
        schemas_api_caller.get_latest_schema_version.return_value = "1"
        schemas_api_caller.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "AWSAPICallViaCloudTrail",
            "schemas_package_hierarchy": "schemas/aws/AWSAPICallViaCloudTrail",
        }
        schema_template_details = get_schema_template_details(schemas_api_caller)
        self.assertEqual(schema_template_details["schema_full_name"], "s25"),
        self.assertEqual(schema_template_details["schema_root_name"], "AWSAPICallViaCloudTrail"),
        self.assertEqual(schema_template_details["registry_name"], "r22")
        self.assertEqual(schema_template_details["schema_version"], "1")
        self.assertEqual(schema_template_details["event_source"], "aws.autoscaling")
        self.assertEqual(schema_template_details["event_source_detail_type"], "aws.autoscaling response")
        self.assertEqual(schema_template_details["schemas_package_hierarchy"], "schemas/aws/AWSAPICallViaCloudTrail")
        prompt_mock.assert_any_call(
            "Schema Registry [Page 1/many] (Enter N for next page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Schema Registry [Page 2/many] (Enter N/P for next/previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Schema Registry [Page 3/3] (Enter P for previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call("Event Schemas [Page 1/many] (Enter N for next page)", type=ANY, show_choices=False)
        prompt_mock.assert_any_call(
            "Event Schemas [Page 2/many] (Enter N/P for next/previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Event Schemas [Page 3/3] (Enter P for previous page)", type=ANY, show_choices=False
        )

    @patch("click.prompt")
    @patch("samcli.lib.schemas.schemas_api_caller.SchemasApiCaller")
    def test_schema_prompt_paginate_with_previous_page_choice(self, schemas_api_caller, prompt_mock):
        prompt_mock.side_effect = ["N", "N", "P", "15", "N", "N", "P", "12"]
        schemas_api_caller.list_registries.side_effect = [
            {"registries": ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10"], "next_token": "1234"},
            {
                "registries": ["r11", "r12", "r13", "r14", "r15", "r16", "r17", "r18", "r19", "r20"],
                "next_token": "1234",
            },
            {"registries": ["r21", "r22", "r23", "r24", "r25", "r26", "r27", "r28", "r29", "r30"], "next_token": None},
        ]
        schemas_api_caller.list_schemas.side_effect = [
            {"schemas": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10"], "next_token": "1234"},
            {"schemas": ["s11", "s12", "s13", "s14", "s15", "s16", "s17", "s18", "s19", "s20"], "next_token": "1234"},
            {"schemas": ["s21", "s22", "s23", "s24", "s25", "s26", "s27", "s28", "s29", "s30"], "next_token": None},
        ]
        schemas_api_caller.get_latest_schema_version.return_value = "1"
        schemas_api_caller.get_schema_metadata.return_value = {
            "event_source": "aws.autoscaling",
            "event_source_detail_type": "aws.autoscaling response",
            "schema_root_name": "AWSAPICallViaCloudTrail",
            "schemas_package_hierarchy": "schemas/aws/AWSAPICallViaCloudTrail",
        }
        schema_template_details = get_schema_template_details(schemas_api_caller)
        self.assertEqual(schema_template_details["schema_full_name"], "s12"),
        self.assertEqual(schema_template_details["schema_root_name"], "AWSAPICallViaCloudTrail"),
        self.assertEqual(schema_template_details["registry_name"], "r15")
        self.assertEqual(schema_template_details["schema_version"], "1")
        self.assertEqual(schema_template_details["event_source"], "aws.autoscaling")
        self.assertEqual(schema_template_details["event_source_detail_type"], "aws.autoscaling response")
        self.assertEqual(schema_template_details["schemas_package_hierarchy"], "schemas/aws/AWSAPICallViaCloudTrail")
        prompt_mock.assert_any_call(
            "Schema Registry [Page 1/many] (Enter N for next page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Schema Registry [Page 2/many] (Enter N/P for next/previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Schema Registry [Page 3/3] (Enter P for previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Schema Registry [Page 2/3] (Enter N/P for next/previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call("Event Schemas [Page 1/many] (Enter N for next page)", type=ANY, show_choices=False)
        prompt_mock.assert_any_call(
            "Event Schemas [Page 2/many] (Enter N/P for next/previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Event Schemas [Page 3/3] (Enter P for previous page)", type=ANY, show_choices=False
        )
        prompt_mock.assert_any_call(
            "Event Schemas [Page 2/3] (Enter N/P for next/previous page)", type=ANY, show_choices=False
        )
