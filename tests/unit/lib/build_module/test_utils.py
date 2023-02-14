from unittest.case import TestCase

from samcli.lib.build.utils import _make_env_vars
from tests.unit.lib.build_module.test_build_graph import generate_function


class TestApplicationBuilder_make_env_vars(TestCase):
    def test_make_env_vars_with_env_file(self):
        function1 = generate_function(name="Function1")
        file_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR2": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = _make_env_vars(function1, file_env_vars, {})
        self.assertEqual(result, {"ENV_VAR1": "1", "ENV_VAR2": "2"})

    def test_make_env_vars_with_function_precedence(self):
        function1 = generate_function(name="Function1")
        file_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR1": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = _make_env_vars(function1, file_env_vars, {})
        self.assertEqual(result, {"ENV_VAR1": "2"})

    def test_make_env_vars_with_inline_env(self):
        function1 = generate_function(name="Function1")
        inline_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR2": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = _make_env_vars(function1, {}, inline_env_vars)
        self.assertEqual(result, {"ENV_VAR1": "1", "ENV_VAR2": "2"})

    def test_make_env_vars_with_both(self):
        function1 = generate_function(name="Function1")
        file_env_vars = {
            "Parameters": {"ENV_VAR1": "1"},
            "Function1": {"ENV_VAR2": "2"},
            "Function2": {"ENV_VAR3": "3"},
        }
        inline_env_vars = {
            "Parameters": {"ENV_VAR1": "2"},
            "Function1": {"ENV_VAR2": "3"},
            "Function2": {"ENV_VAR3": "3"},
        }
        result = _make_env_vars(function1, file_env_vars, inline_env_vars)
        self.assertEqual(result, {"ENV_VAR1": "2", "ENV_VAR2": "3"})
