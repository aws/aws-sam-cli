"""Unit tests for resolve_language_extensions_enabled()."""

import os
from unittest import mock

import pytest

from samcli.lib.cfn_language_extensions.sam_integration import (
    ENABLE_ENV_VAR,
    resolve_language_extensions_enabled,
)


class TestResolveLanguageExtensionsEnabled:
    """Flag-vs-env precedence and truthy parsing."""

    def test_flag_true_returns_true(self):
        with mock.patch.dict(os.environ, {ENABLE_ENV_VAR: ""}, clear=False):
            assert resolve_language_extensions_enabled(True) is True

    def test_flag_false_returns_false(self):
        with mock.patch.dict(os.environ, {ENABLE_ENV_VAR: "1"}, clear=False):
            # Flag wins over env var.
            assert resolve_language_extensions_enabled(False) is False

    def test_flag_none_with_env_unset_returns_false(self):
        env = {k: v for k, v in os.environ.items() if k != ENABLE_ENV_VAR}
        with mock.patch.dict(os.environ, env, clear=True):
            assert resolve_language_extensions_enabled(None) is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES", "Yes"])
    def test_flag_none_with_truthy_env_returns_true(self, value):
        with mock.patch.dict(os.environ, {ENABLE_ENV_VAR: value}, clear=False):
            assert resolve_language_extensions_enabled(None) is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "maybe", "", "  ", "2"])
    def test_flag_none_with_untruthy_env_returns_false(self, value):
        with mock.patch.dict(os.environ, {ENABLE_ENV_VAR: value}, clear=False):
            assert resolve_language_extensions_enabled(None) is False

    def test_flag_none_with_whitespace_env_is_stripped(self):
        with mock.patch.dict(os.environ, {ENABLE_ENV_VAR: "  true  "}, clear=False):
            assert resolve_language_extensions_enabled(None) is True
