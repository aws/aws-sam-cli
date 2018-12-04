
from unittest import TestCase
from mock import Mock

from samcli.local.lambdafn.config import FunctionConfig


class TestFunctionConfig(TestCase):

    DEFAULT_MEMORY = 128
    DEFAULT_TIMEOUT = 3

    def setUp(self):
        self.name = "name"
        self.runtime = "runtime"
        self.handler = "handler"
        self.code_path = "codepath"
        self.memory = 1234
        self.timeout = 34
        self.env_vars_mock = Mock()
        self.layers = ['layer1']

    def test_init_with_env_vars(self):
        config = FunctionConfig(self.name, self.runtime, self.handler, self.code_path, self.layers,
                                memory=self.memory, timeout=self.timeout, env_vars=self.env_vars_mock)

        self.assertEquals(config.name, self.name)
        self.assertEquals(config.runtime, self.runtime)
        self.assertEquals(config.handler, self.handler)
        self.assertEquals(config.code_abs_path, self.code_path)
        self.assertEquals(config.layers, self.layers)
        self.assertEquals(config.memory, self.memory)
        self.assertEquals(config.timeout, self.timeout)
        self.assertEquals(config.env_vars, self.env_vars_mock)

        self.assertEquals(self.env_vars_mock.handler, self.handler)
        self.assertEquals(self.env_vars_mock.memory, self.memory)
        self.assertEquals(self.env_vars_mock.timeout, self.timeout)

    def test_init_without_optional_values(self):
        config = FunctionConfig(self.name, self.runtime, self.handler, self.code_path, self.layers)

        self.assertEquals(config.name, self.name)
        self.assertEquals(config.runtime, self.runtime)
        self.assertEquals(config.handler, self.handler)
        self.assertEquals(config.code_abs_path, self.code_path)
        self.assertEquals(config.layers, self.layers)
        self.assertEquals(config.memory, self.DEFAULT_MEMORY)
        self.assertEquals(config.timeout, self.DEFAULT_TIMEOUT)
        self.assertIsNotNone(config.env_vars)

        self.assertEquals(config.env_vars.handler, self.handler)
        self.assertEquals(config.env_vars.memory, self.DEFAULT_MEMORY)
        self.assertEquals(config.env_vars.timeout, self.DEFAULT_TIMEOUT)
