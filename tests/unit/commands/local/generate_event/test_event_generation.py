import os

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.lib.generated_sample_events import events
from samcli.commands.local.generate_event.event_generation import ServiceCommand
from samcli.commands.local.generate_event.event_generation import EventTypeSubCommand


class TestEvents(TestCase):
    def setUp(self):
        self.values_to_sub = {"hello": "world"}

    def test_base64_encoding(self):
        result = events.Events().encode("base64", "world")
        self.assertEqual(result, "d29ybGQ=")

    def test_url_encoding(self):
        result = events.Events().encode("url", "http://www.example.com/?a=1&b=2")
        self.assertEqual(result, "http%3A//www.example.com/%3Fa%3D1%26b%3D2")

    def test_if_encoding_is_none(self):
        result = events.Events().encode(None, "hello")
        self.assertEqual(result, "hello")

    def test_if_encoding_is_other(self):
        result = events.Events().encode("other", "hello")
        self.assertEqual(result, "hello")

    def test_md5_hashing(self):
        result = events.Events().hash("md5", "hello, world!")
        self.assertEqual(result, "3adbbad1791fbae3ec908894c4963870")

    def test_if_hashing_is_not_supported(self):
        self.assertRaises(ValueError, events.Events().hash, "unsupported", "hello, world!")

    def test_transform_val_encoding(self):
        properties = {"encoding": "base64"}
        val = "world"
        result = events.Events().transform_val(properties, val)
        self.assertEqual(result, "d29ybGQ=")

    def test_transform_val_hashing(self):
        properties = {"hashing": "md5"}
        val = "hello, world!"
        result = events.Events().transform_val(properties, val)
        self.assertEqual(result, "3adbbad1791fbae3ec908894c4963870")

    def test_transform_val_both(self):
        properties = {"encoding": "url", "hashing": "md5"}
        val = "http://www.example.com/?a=1&b=2"
        result = events.Events().transform_val(properties, val)
        self.assertEqual(result, "d878d5aa4c79b8f2b3e2c5d4e9d45beb")

    def test_transform(self):
        tags = {
            "hello": {"encoding": "base64"},
            "url": {"encoding": "url"},
            "foo": {"children": {"baz": {"hashing": "md5"}}},
        }
        values_to_sub = {
            "hello": "world",
            "url": "http://www.example.com/?a=1&b=2",
            "foo": "bar",
        }
        result = events.Events().transform(tags, values_to_sub)
        expected = {
            "hello": "d29ybGQ=",
            "url": "http%3A//www.example.com/%3Fa%3D1%26b%3D2",
            "foo": "bar",
            "baz": "37b51d194a7513e45b56f6524f2d51f2",
        }
        self.assertEqual(result, expected)

    def test_transform_val_dict_type_kept_as_string(self):
        """Test that dict type values are kept as strings during transform"""
        properties = {"type": "dict"}
        val = '{"key1": "value1", "key2": "value2"}'
        result = events.Events().transform_val(properties, val)
        # Should remain a string for template rendering
        self.assertEqual(result, val)
        self.assertIsInstance(result, str)

    def test_generate_event_with_dict_value(self):
        """Test that generate_event properly handles dictionary values"""
        events_lib = events.Events()
        # Test with apigateway aws-proxy which has querystringparameters as dict type
        # Pass as JSON string (as it would come from CLI)
        result = events_lib.generate_event(
            "apigateway",
            "aws-proxy",
            {
                "method": "GET",
                "path": "test",
                "body": "",
                "querystringparameters": '{"documentId": "1044", "versionId": "v_1"}',
            },
        )
        import json

        result_json = json.loads(result)
        # Verify that queryStringParameters is a dict, not a string
        self.assertIsInstance(result_json["queryStringParameters"], dict)
        self.assertEqual(result_json["queryStringParameters"]["documentId"], "1044")
        self.assertEqual(result_json["queryStringParameters"]["versionId"], "v_1")

    def test_generate_event_with_complex_dict_value(self):
        """Test that generate_event handles complex dict values with special characters"""
        events_lib = events.Events()
        # Test with complex JSON including special characters
        result = events_lib.generate_event(
            "apigateway",
            "aws-proxy",
            {
                "method": "POST",
                "path": "api/search",
                "body": "",
                "querystringparameters": '{"filter": "status=active", "sort": "desc", "limit": "10"}',
            },
        )
        import json

        result_json = json.loads(result)
        # Verify complex dict is properly parsed
        self.assertIsInstance(result_json["queryStringParameters"], dict)
        self.assertEqual(result_json["queryStringParameters"]["filter"], "status=active")
        self.assertEqual(result_json["queryStringParameters"]["sort"], "desc")
        self.assertEqual(result_json["queryStringParameters"]["limit"], "10")


class TestServiceCommand(TestCase):
    def setUp(self):
        self.service_cmd_name = "myservice"
        self.event_type_name = "myevent"
        self.all_cmds = {"hello": "world", "hi": "you"}
        self.events_lib_mock = Mock()
        self.events_lib_mock.event_mapping = self.all_cmds
        self.s = ServiceCommand(self.events_lib_mock)

    def test_init_has_correct_all_cmds(self):
        self.assertEqual(self.s.all_cmds, self.all_cmds)

    def test_init_events_lib_is_not_valid(self):
        with self.assertRaises(ValueError):
            ServiceCommand(events_lib=None)

    def test_init_events_lib_is_valid(self):
        s = ServiceCommand(self.events_lib_mock)
        self.assertEqual(s.events_lib, self.events_lib_mock)

    def test_get_command_returns_none_when_not_in_all_cmds(self):
        cmd_name = "howdy"
        e = self.s.get_command(None, cmd_name)
        self.assertIsNone(e)

    def test_list_commands_must_return_commands_name(self):
        expected = self.s.list_commands(ctx=None)
        self.assertEqual(expected, ["hello", "hi"])

    def test_get_command_return_value(self):
        command_name = "hello"
        output = self.s.get_command(None, command_name)
        self.assertEqual(output.top_level_cmd_name, "hello")
        self.assertEqual(output.events_lib, self.events_lib_mock)
        self.assertEqual(output.subcmd_definition, "world")


class TestEventTypeSubCommand(TestCase):
    def setUp(self):
        self.service_cmd_name = "myservice"
        self.event_type_name = "myevent"
        self.all_cmds = '{"hello": "world", "hi": "you"}'
        self.events_lib_mock = Mock()
        self.s = EventTypeSubCommand(self.events_lib_mock, self.service_cmd_name, self.all_cmds)

        # Disable telemetry
        self.old_environ = os.environ.copy()
        os.environ["SAM_CLI_TELEMETRY"] = "0"

    def tearDown(self):
        os.environ = self.old_environ

    def test_subcommand_accepts_events_lib(self):
        events_lib = Mock()
        events_lib.expose_event_metadata.return_value = self.all_cmds
        s = EventTypeSubCommand(events_lib, self.service_cmd_name, self.all_cmds)
        self.assertEqual(s.events_lib, events_lib)

    def test_subcommand_accepts_top_level_cmd_name(self):
        top_lvl_cmd = "myservice"
        self.assertEqual(top_lvl_cmd, self.service_cmd_name)

    def test_subcommand_accepts_subcmd_definition(self):
        self.assertEqual(self.s.subcmd_definition, self.all_cmds)

    def test_subcommand_get_accepts_cmd_name_returns_none(self):
        subcmd_definition = '{"hello": { "tags : { "world" }}}'
        s = EventTypeSubCommand(self.events_lib_mock, self.service_cmd_name, subcmd_definition)
        e = s.get_command(None, "heyyo")
        self.assertIsNone(e)

    @patch("samcli.cli.options.click")
    @patch("samcli.commands.local.generate_event.event_generation.functools")
    @patch("samcli.commands.local.generate_event.event_generation.click")
    def test_subcommand_get_command_return_value(self, click_mock, functools_mock, options_click_mock):
        all_commands = {"hi": {"help": "Generates a hello Event", "tags": {}}}
        command_object_mock = Mock()
        click_mock.Command.return_value = command_object_mock
        option_mock = Mock()
        options_click_mock.Option.return_value = option_mock
        callback_object_mock = Mock()
        functools_mock.partial.return_value = callback_object_mock
        s = EventTypeSubCommand(self.events_lib_mock, "hello", all_commands)
        s.get_command(None, "hi")
        click_mock.Command.assert_called_once_with(
            name="hi",
            short_help="Generates a hello Event",
            params=[],
            callback=callback_object_mock,
        )

    def test_subcommand_list_return_value(self):
        subcmd_def = {"hello": "world", "hi": "you"}
        self.events_lib_mock.expose_event_metadata.return_value = subcmd_def
        s = EventTypeSubCommand(self.events_lib_mock, "hello", subcmd_def)
        expected = ["hello", "hi"]
        self.assertEqual(s.list_commands(ctx=None), expected)

    def test_must_print_sample_event_json(self):
        event_json = '{"hello": "world"}'
        self.events_lib_mock.generate_event.return_value = event_json
        s = EventTypeSubCommand(self.events_lib_mock, "hello", event_json)
        event = s.cmd_implementation(self.events_lib_mock, self.service_cmd_name, self.event_type_name, {})
        self.events_lib_mock.generate_event.assert_called_with(self.service_cmd_name, self.event_type_name, {})
        self.assertEqual(event, event_json)

    def test_must_accept_keyword_args(self):
        event_json = '{"hello": "world"}'
        self.events_lib_mock.generate_event.return_value = event_json
        s = EventTypeSubCommand(self.events_lib_mock, "hello", event_json)
        event = s.cmd_implementation(self.events_lib_mock, self.service_cmd_name, self.event_type_name, key="value")
        self.events_lib_mock.generate_event.assert_called_with(
            self.service_cmd_name, self.event_type_name, {"key": "value"}
        )
        self.assertEqual(event, event_json)
