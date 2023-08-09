from typing import List
from unittest.mock import MagicMock, patch
from parameterized import parameterized
from unittest import TestCase
from schema.exceptions import SchemaGenerationException

from schema.make_schema import (
    SamCliCommandSchema,
    SamCliParameterSchema,
    SchemaKeys,
    format_param,
    generate_schema,
    get_params_from_command,
    retrieve_command_structure,
)


class TestParameterSchema(TestCase):
    @parameterized.expand(
        [
            ("", "", {}),
            ("default", "default value", {"default": "default value"}),
            ("items", "item type", {"items": {"type": "item type"}}),
            ("choices", ["1", "2"], {"enum": ["1", "2"]}),
        ]
    )
    def test_parameter_to_schema(self, property_name, property_value, added_property_field):
        param = SamCliParameterSchema("param name", "param type", "param description")
        param.__setattr__(property_name, property_value)

        param_schema = param.to_schema()

        expected_schema = {"title": "param name", "type": "param type", "description": "param description"}
        expected_schema.update(added_property_field)
        self.assertEqual(expected_schema, param_schema)

    def test_parameter_to_schema_with_multiple_type(self):
        param = SamCliParameterSchema("param name", ["type1", "type2"], "param description")

        param_schema = param.to_schema()

        expected_schema = {"title": "param name", "type": ["type1", "type2"], "description": "param description"}
        self.assertEqual(expected_schema, param_schema)


class TestCommandSchema(TestCase):
    def test_command_to_schema(self):
        params = [SamCliParameterSchema("param1", "string"), SamCliParameterSchema("param2", "number")]
        command = SamCliCommandSchema("commandname", "command description", params)

        command_schema = command.to_schema()

        self.assertEqual(len(command_schema.keys()), 1)
        self.assertEqual(list(command_schema.keys())[0], "commandname")
        inner_schema = command_schema["commandname"]
        self._validate_schema_keys(inner_schema)
        self._validate_schema_parameters_keys(inner_schema)
        self._validate_schema_parameters_exist_correctly(inner_schema, params)
        self.assertEqual(["parameters"], inner_schema["required"], "Parameters attribute should be required")

    def _validate_schema_keys(self, schema):
        for expected_key in ["title", "description", "properties", "required"]:
            self.assertIn(expected_key, schema.keys(), f"Command schema should have key {expected_key}")
        self.assertIn("parameters", schema["properties"].keys(), "Schema should have 'parameters'")

    def _validate_schema_parameters_keys(self, schema):
        for expected_key in ["title", "description", "type", "properties"]:
            self.assertIn(
                expected_key,
                schema["properties"]["parameters"],
                f"Parameters schema should have key {expected_key}",
            )

    def _validate_schema_parameters_exist_correctly(self, schema, expected_params):
        for param in expected_params:
            self.assertIn(
                param.name, schema["properties"]["parameters"]["properties"], f"{param.name} should be in schema"
            )
            self.assertEqual(
                param.to_schema(),
                schema["properties"]["parameters"]["properties"].get(param.name),
                f"{param.name} should point to schema representation",
            )


class TestSchemaLogic(TestCase):
    @parameterized.expand(
        [
            ("string", "string"),
            ("integer", "integer"),
            ("number", "number"),
            ("text", "string"),
            ("path", "string"),
            ("choice", "string"),
            ("filename", "string"),
            ("directory", "string"),
            ("LIST", "array"),
            ("type1,type2", ["type1", "type2"]),
            ("list,type1", ["array", "type1"]),
            ("string,path,choice,filename,directory", "string"),
        ]
    )
    def test_param_formatted_correctly(self, param_type, expected_type):
        mock_param = MagicMock()
        mock_param.name = "param_name"
        mock_param.type.name = param_type
        mock_param.help = "param description"
        mock_param.default = None

        formatted_param = format_param(mock_param)

        self.assertIsInstance(formatted_param, SamCliParameterSchema)
        self.assertEqual(formatted_param.name, "param_name")
        self.assertEqual(formatted_param.type, expected_type)
        self.assertEqual(formatted_param.description, "param description")
        self.assertEqual(formatted_param.default, None)

    def test_param_formatted_throws_error_when_none(self):
        mock_param = MagicMock()
        mock_param.type.name = None

        with self.assertRaises(SchemaGenerationException):
            format_param(None)

        with self.assertRaises(SchemaGenerationException):
            format_param(mock_param)

    @parameterized.expand(
        [
            ("list", SamCliParameterSchema("p_name", "array", default="default value", items="string")),
            ("choice", SamCliParameterSchema("p_name", "string", default=["default", "value"], choices=["1", "2"])),
        ]
    )
    @patch("schema.make_schema.isinstance")
    def test_param_formatted_given_type(self, param_type, expected_param, isinstance_mock):
        mock_param = MagicMock()
        mock_param.name = "p_name"
        mock_param.type.name = param_type
        mock_param.type.choices = ["1", "2"]
        mock_param.help = None
        mock_param.default = ("default", "value") if param_type == "choice" else "default value"
        isinstance_mock.return_value = True if param_type == "choice" else False  # mock check against click.Choice

        formatted_param = format_param(mock_param)

        self.assertEqual(expected_param, formatted_param)

    @patch("schema.make_schema.isinstance")
    @patch("schema.make_schema.format_param")
    def test_getting_params_from_cli_object(self, format_param_mock, isinstance_mock):
        mock_cli = MagicMock()
        mock_cli.params = []
        param_names = ["param1", "param2", "config_file", None]
        for param_name in param_names:
            mock_param = MagicMock()
            mock_param.name = param_name
            mock_cli.params.append(mock_param)
        format_param_mock.side_effect = lambda x: x.name

        params = get_params_from_command(mock_cli)

        self.assertIn("param1", params)
        self.assertIn("param2", params)
        self.assertNotIn("config_file", params)
        self.assertNotIn(None, params)

    @patch("schema.make_schema.importlib.import_module")
    @patch("schema.make_schema.get_params_from_command")
    def test_command_structure_is_retrieved(self, get_params_mock, import_mock):
        mock_module = self._setup_mock_module()
        import_mock.side_effect = lambda _: mock_module
        get_params_mock.return_value = []

        commands = retrieve_command_structure("")

        self._validate_retrieved_command_structure(commands)

    @patch("schema.make_schema.importlib.import_module")
    @patch("schema.make_schema.get_params_from_command")
    @patch("schema.make_schema.isinstance")
    def test_command_structure_is_retrieved_from_group_cli(self, isinstance_mock, get_params_mock, import_mock):
        mock_module = self._setup_mock_module()
        mock_module.cli.commands = {}
        for i in range(2):
            mock_subcommand = MagicMock()
            mock_subcommand.name = f"subcommand{i}"
            mock_subcommand.help = "help text"
            mock_module.cli.commands.update({f"subcommand{i}": mock_subcommand})
        import_mock.side_effect = lambda _: mock_module
        get_params_mock.return_value = []

        commands = retrieve_command_structure("")

        self._validate_retrieved_command_structure(commands)

    @patch("schema.make_schema.retrieve_command_structure")
    def test_schema_is_generated_properly(self, retrieve_commands_mock):
        def mock_retrieve_commands(package_name, counter=[0]):
            counter[0] += 1
            return [SamCliCommandSchema(f"command-{counter[0]}", "some command", [])]

        retrieve_commands_mock.side_effect = mock_retrieve_commands

        schema = generate_schema()

        for expected_key in [
            "$schema",
            "title",
            "type",
            "properties",
            "required",
            "additionalProperties",
            "patternProperties",
        ]:
            self.assertIn(expected_key, schema.keys(), f"Key '{expected_key}' should be in schema")
        self.assertEqual(schema["required"], ["version"], "Version key should be required")
        self.assertEqual(
            list(schema["patternProperties"].keys()),
            [SchemaKeys.ENVIRONMENT_REGEX.value],
            "patternProperties should have environment regex value",
        )
        self.assertEqual(
            list(schema["patternProperties"][SchemaKeys.ENVIRONMENT_REGEX.value].keys()),
            ["title", "properties"],
            "Environment should have keys 'title' and 'properties'",
        )
        commands_in_schema = schema["patternProperties"][SchemaKeys.ENVIRONMENT_REGEX.value]["properties"]
        for command_name, command_value in commands_in_schema.items():
            self.assertTrue(command_name.startswith("command-"), "Command should have key of its name")
            command_number = command_name.split("-")[-1]
            self.assertEqual(
                {command_name: command_value},
                SamCliCommandSchema(f"command-{command_number}", "some command", []).to_schema(),
                "Command should be represented correctly in schema",
            )

    def _setup_mock_module(self) -> MagicMock:
        mock_module = MagicMock()
        mock_module.__setattr__("__name__", "samcli.commands.cmdname")
        mock_module.cli.help = "help text"
        return mock_module

    def _validate_retrieved_command_structure(self, commands: List[SamCliCommandSchema]):
        for command in commands:
            self.assertTrue(command.name.startswith("cmdname"), "Name of command should be parsed")
            self.assertEqual(command.description, "help text", "Help text should be parsed")
