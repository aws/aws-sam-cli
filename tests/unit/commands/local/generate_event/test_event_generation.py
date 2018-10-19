from unittest import TestCase
from mock import Mock
from mock import patch

from samcli.commands.local.lib.generated_sample_events import events
from samcli.commands.local.generate_event.event_generation import ServiceCommand
from samcli.commands.local.generate_event.event_generation import EventTypeSubCommand


class TestEvents(TestCase):

    def setUp(self):
        self.values_to_sub = {"hello": "world"}

    def test_base64_encoding(self):
        tags = {"hello": {"encoding": "base64"}}
        e = events.Events().encode(tags, 'encoding', self.values_to_sub)
        self.assertEqual(e, {"hello": "d29ybGQ="})

    def test_url_encoding(self):
        tags = {"hello": {"encoding": "url"}}
        e = events.Events().encode(tags, 'encoding', self.values_to_sub)
        self.assertEqual(e, {"hello": "world"})

    def test_if_encoding_is_none(self):
        tags = {"hello": {"encoding": "None"}}
        e = events.Events().encode(tags, 'encoding', self.values_to_sub)
        self.assertEqual(e, {"hello": "world"})

    def test_if_tags_is_empty(self):
        tags = {}
        e = events.Events().encode(tags, 'encoding', {})
        self.assertEqual(e, {})

    def test_if_tags_is_two_or_more(self):
        tags = {"hello": {"encoding": "base64"}, "hi": {"encoding": "url"}, "bop": {"encoding": "None"}}
        values_to_sub = {"bop": "dop", "hello": "world", "hi": "yo"}
        e = events.Events().encode(tags, 'encoding', values_to_sub)
        self.assertEqual(e, {"bop": "dop", "hello": "d29ybGQ=", "hi": "yo"})


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
        self.assertEqual(expected, ['hello', 'hi'])

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
        click_mock.Command.assert_called_once_with(name="hi",
                                                   short_help="Generates a hello Event",
                                                   params=[],
                                                   callback=callback_object_mock)

    def test_subcommand_list_return_value(self):
        subcmd_def = {"hello": "world", "hi": "you"}
        self.events_lib_mock.expose_event_metadata.return_value = subcmd_def
        s = EventTypeSubCommand(self.events_lib_mock, "hello", subcmd_def)
        expected = ['hello', 'hi']
        self.assertEquals(s.list_commands(ctx=None), expected)

    def test_must_print_sample_event_json(self):
        event_json = '{"hello": "world"}'
        self.events_lib_mock.generate_event.return_value = event_json
        s = EventTypeSubCommand(self.events_lib_mock, "hello", event_json)
        event = s.cmd_implementation(self.events_lib_mock,
                                     self.service_cmd_name,
                                     self.event_type_name,
                                     {})
        self.events_lib_mock.generate_event.assert_called_with(self.service_cmd_name,
                                                               self.event_type_name,
                                                               {})
        self.assertEqual(event, event_json)

    def test_must_accept_keyword_args(self):
        event_json = '{"hello": "world"}'
        self.events_lib_mock.generate_event.return_value = event_json
        s = EventTypeSubCommand(self.events_lib_mock, "hello", event_json)
        event = s.cmd_implementation(self.events_lib_mock,
                                     self.service_cmd_name,
                                     self.event_type_name,
                                     key="value")
        self.events_lib_mock.generate_event.assert_called_with(self.service_cmd_name,
                                                               self.event_type_name,
                                                               {"key": "value"})
        self.assertEqual(event, event_json)
