from unittest import TestCase

from samcli.lib.schemas.schemas_cli_message_generator import (
    construct_cli_display_message_for_schemas,
    construct_cli_display_message_for_registries,
)


class TestSchemasCLIMessageGenerator(TestCase):
    def test_construct_cli_display_message_for_schemas(self):
        cli_display_message = construct_cli_display_message_for_schemas(2, None)
        self.assertEqual(cli_display_message["last_page"], "Event Schemas [Page 2/many] (Enter P for previous page)")
        self.assertEqual(
            cli_display_message["middle_page"], "Event Schemas [Page 2/many] (Enter N/P for next/previous page)"
        )
        self.assertEqual(cli_display_message["first_page"], "Event Schemas [Page 2/many] (Enter N for next page)")
        self.assertEqual(cli_display_message["single_page"], "Event Schemas")

    def test_construct_cli_display_message_for_registries(self):
        cli_display_message = construct_cli_display_message_for_registries(2, None)
        self.assertEqual(cli_display_message["last_page"], "Schema Registry [Page 2/many] (Enter P for previous page)")
        self.assertEqual(
            cli_display_message["middle_page"], "Schema Registry [Page 2/many] (Enter N/P for next/previous page)"
        )
        self.assertEqual(cli_display_message["first_page"], "Schema Registry [Page 2/many] (Enter N for next page)")
        self.assertEqual(cli_display_message["single_page"], "Schema Registry")
