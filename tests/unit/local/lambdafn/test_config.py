from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.lib.utils.packagetype import ZIP
from samcli.local.lambdafn.config import FunctionConfig
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException


class TestFunctionConfig(TestCase):

    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.name = "name"
        self.full_path = "stack/name"
        self.runtime = "runtime"
        self.handler = "handler"
        self.imageuri = None
        self.imageconfig = None
        self.packagetype = ZIP
        self.code_path = "codepath"
        self.memory = 1234
        self.timeout = 34
        self.env_vars_mock = Mock()
        self.layers = ["layer1"]
        self.architecture = "arm64"

    def test_init_with_env_vars(self):
        config = FunctionConfig(
            self.name,
            self.full_path,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
            memory=self.memory,
            timeout=self.timeout,
            env_vars=self.env_vars_mock,
        )

        self.assertEqual(config.name, self.name)
        self.assertEqual(config.full_path, self.full_path)
        self.assertEqual(config.runtime, self.runtime)
        self.assertEqual(config.handler, self.handler)
        self.assertEqual(config.imageuri, self.imageuri)
        self.assertEqual(config.imageconfig, self.imageconfig)
        self.assertEqual(config.packagetype, self.packagetype)
        self.assertEqual(config.code_abs_path, self.code_path)
        self.assertEqual(config.layers, self.layers)
        self.assertEqual(config.memory, self.memory)
        self.assertEqual(config.timeout, self.timeout)
        self.assertEqual(config.env_vars, self.env_vars_mock)

        self.assertEqual(self.env_vars_mock.handler, self.handler)
        self.assertEqual(self.env_vars_mock.memory, self.memory)
        self.assertEqual(self.env_vars_mock.timeout, self.timeout)

    def test_init_without_optional_values(self):
        config = FunctionConfig(
            self.name,
            self.full_path,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
        )

        self.assertEqual(config.name, self.name)
        self.assertEqual(config.full_path, self.full_path)
        self.assertEqual(config.runtime, self.runtime)
        self.assertEqual(config.handler, self.handler)
        self.assertEqual(config.packagetype, self.packagetype)
        self.assertEqual(config.imageuri, self.imageuri)
        self.assertEqual(config.imageconfig, self.imageconfig)
        self.assertEqual(config.code_abs_path, self.code_path)
        self.assertEqual(config.layers, self.layers)
        self.assertEqual(config.memory, self.DEFAULT_MEMORY)
        self.assertEqual(config.timeout, self.DEFAULT_TIMEOUT)
        self.assertIsNotNone(config.env_vars)

        self.assertEqual(config.env_vars.handler, self.handler)
        self.assertEqual(config.env_vars.memory, self.DEFAULT_MEMORY)
        self.assertEqual(config.env_vars.timeout, self.DEFAULT_TIMEOUT)

    def test_init_with_timeout_of_int_string(self):
        config = FunctionConfig(
            self.name,
            self.full_path,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
            memory=self.memory,
            timeout="34",
            env_vars=self.env_vars_mock,
        )

        self.assertEqual(config.name, self.name)
        self.assertEqual(config.full_path, self.full_path)
        self.assertEqual(config.runtime, self.runtime)
        self.assertEqual(config.handler, self.handler)
        self.assertEqual(config.packagetype, self.packagetype)
        self.assertEqual(config.imageuri, self.imageuri)
        self.assertEqual(config.imageconfig, self.imageconfig)
        self.assertEqual(config.code_abs_path, self.code_path)
        self.assertEqual(config.layers, self.layers)
        self.assertEqual(config.memory, self.memory)
        self.assertEqual(config.timeout, 34)
        self.assertEqual(config.env_vars, self.env_vars_mock)

        self.assertEqual(self.env_vars_mock.handler, self.handler)
        self.assertEqual(self.env_vars_mock.memory, self.memory)
        self.assertEqual(self.env_vars_mock.timeout, 34)


class TestFunctionConfigInvalidTimeouts(TestCase):
    def setUp(self):
        self.name = "name"
        self.full_path = "stack/name"
        self.runtime = "runtime"
        self.handler = "handler"
        self.imageuri = None
        self.imageconfig = None
        self.packagetype = ZIP
        self.code_path = "codepath"
        self.memory = 1234
        self.env_vars_mock = Mock()
        self.layers = ["layer1"]
        self.architecture = "x86_64"

    @parameterized.expand(
        [
            ("none int string",),
            ({"dictionary": "is not a string either"},),
            ("/local/lambda/timeout",),
            ("3.2",),
            ("4.2",),
            ("0.123",),
        ]
    )
    def test_init_with_invalid_timeout_values(self, timeout):
        with self.assertRaises(InvalidSamTemplateException):
            FunctionConfig(
                self.name,
                self.full_path,
                self.runtime,
                self.imageuri,
                self.handler,
                self.packagetype,
                self.imageconfig,
                self.code_path,
                self.layers,
                self.architecture,
                memory=self.memory,
                timeout=timeout,
                env_vars=self.env_vars_mock,
            )


class TestFunctionConfig_equals(TestCase):

    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.name = "name"
        self.full_path = "stack/name"
        self.name2 = "name2"
        self.full_path2 = "stack/name2"
        self.runtime = "runtime"
        self.handler = "handler"
        self.imageuri = None
        self.imageconfig = None
        self.packagetype = ZIP
        self.code_path = "codepath"
        self.memory = 1234
        self.timeout = 34
        self.env_vars_mock = Mock()
        self.layers = ["layer1"]
        self.architecture = "arm64"

    def test_equals_function_config(self):
        config1 = FunctionConfig(
            self.name,
            self.full_path,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
            memory=self.memory,
            timeout=self.timeout,
            env_vars=self.env_vars_mock,
        )

        config2 = FunctionConfig(
            self.name,
            self.full_path,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
            memory=self.memory,
            timeout=self.timeout,
            env_vars=self.env_vars_mock,
        )

        self.assertTrue(config1 == config2)

    def test_not_equals_function_config(self):
        config1 = FunctionConfig(
            self.name,
            self.full_path,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
            memory=self.memory,
            timeout=self.timeout,
            env_vars=self.env_vars_mock,
        )

        config2 = FunctionConfig(
            self.name2,
            self.full_path2,
            self.runtime,
            self.handler,
            self.imageuri,
            self.imageconfig,
            self.packagetype,
            self.code_path,
            self.layers,
            self.architecture,
            memory=self.memory,
            timeout=self.timeout,
            env_vars=self.env_vars_mock,
        )

        self.assertTrue(config1 != config2)
