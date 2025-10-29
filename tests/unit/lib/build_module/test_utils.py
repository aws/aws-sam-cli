from unittest.case import TestCase
from unittest.mock import patch, MagicMock

from samcli.lib.build.utils import (
    _make_env_vars,
    _get_host_architecture,
    _get_function_architecture,
    warn_cross_architecture_build,
)
from samcli.lib.utils.architecture import ARM64, X86_64
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


class TestArchitectureDetection(TestCase):
    @patch("platform.machine")
    def test_get_host_architecture_arm64(self, mock_machine):
        """Test ARM64 host architecture detection."""
        mock_machine.return_value = "arm64"
        result = _get_host_architecture()
        self.assertEqual(result, ARM64)

    @patch("platform.machine")
    def test_get_host_architecture_aarch64(self, mock_machine):
        """Test ARM64 host architecture detection with aarch64."""
        mock_machine.return_value = "aarch64"
        result = _get_host_architecture()
        self.assertEqual(result, ARM64)

    @patch("platform.machine")
    def test_get_host_architecture_x86_64(self, mock_machine):
        """Test x86_64 host architecture detection."""
        mock_machine.return_value = "x86_64"
        result = _get_host_architecture()
        self.assertEqual(result, X86_64)

    @patch("platform.machine")
    def test_get_host_architecture_amd64(self, mock_machine):
        """Test x86_64 host architecture detection with amd64."""
        mock_machine.return_value = "amd64"
        result = _get_host_architecture()
        self.assertEqual(result, X86_64)

    @patch("platform.machine")
    def test_get_host_architecture_case_insensitive(self, mock_machine):
        """Test host architecture detection is case insensitive."""
        mock_machine.return_value = "ARM64"
        result = _get_host_architecture()
        self.assertEqual(result, ARM64)

    @patch("platform.machine")
    def test_get_host_architecture_unknown_defaults_to_x86_64(self, mock_machine):
        """Test unknown host architecture defaults to x86_64."""
        mock_machine.return_value = "unknown"
        result = _get_host_architecture()
        self.assertEqual(result, X86_64)

    def test_get_function_architecture_with_architectures(self):
        """Test function architecture extraction when architectures is set."""
        function = generate_function(name="TestFunction", architectures=[ARM64])
        result = _get_function_architecture(function)
        self.assertEqual(result, ARM64)

    def test_get_function_architecture_with_x86_64(self):
        """Test function architecture extraction with x86_64."""
        function = generate_function(name="TestFunction", architectures=[X86_64])
        result = _get_function_architecture(function)
        self.assertEqual(result, X86_64)

    def test_get_function_architecture_without_architectures(self):
        """Test function architecture defaults to x86_64 when not specified."""
        function = generate_function(name="TestFunction", architectures=None)
        result = _get_function_architecture(function)
        self.assertEqual(result, X86_64)

    def test_get_function_architecture_empty_architectures(self):
        """Test function architecture defaults to x86_64 when architectures is empty."""
        function = generate_function(name="TestFunction", architectures=[])
        result = _get_function_architecture(function)
        self.assertEqual(result, X86_64)

    def test_get_function_architecture_multiple_architectures_uses_first(self):
        """Test function architecture uses first architecture when multiple are specified."""
        function = generate_function(name="TestFunction", architectures=[ARM64, X86_64])
        result = _get_function_architecture(function)
        self.assertEqual(result, ARM64)


class TestCrossArchitectureWarning(TestCase):
    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_warns_arm64_host_x86_64_function(self, mock_get_host_arch, mock_log):
        """Test warning for ARM64 host building x86_64 function."""
        mock_get_host_arch.return_value = ARM64
        function = generate_function(name="TestFunction", architectures=[X86_64])

        warn_cross_architecture_build([function], "finch")

        mock_log.warning.assert_called_once_with(
            "Cross-architecture build detected: Building %s function '%s' on %s host. "
            "This may cause build failures with %s. "
            "Consider updating the function architecture to '%s' in template.yaml",
            X86_64,
            "TestFunction",
            ARM64,
            "finch",
            ARM64,
        )

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_warns_x86_64_host_arm64_function(self, mock_get_host_arch, mock_log):
        """Test warning for x86_64 host building ARM64 function."""
        mock_get_host_arch.return_value = X86_64
        function = generate_function(name="TestFunction", architectures=[ARM64])

        warn_cross_architecture_build([function], "docker")

        mock_log.warning.assert_called_once_with(
            "Cross-architecture build detected: Building %s function '%s' on %s host. "
            "This may cause build failures with %s. "
            "Consider updating the function architecture to '%s' in template.yaml",
            ARM64,
            "TestFunction",
            X86_64,
            "docker",
            X86_64,
        )

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_no_warning_matching_architectures_arm64(self, mock_get_host_arch, mock_log):
        """Test no warning when ARM64 host matches ARM64 function."""
        mock_get_host_arch.return_value = ARM64
        function = generate_function(name="TestFunction", architectures=[ARM64])

        warn_cross_architecture_build([function], "finch")

        mock_log.warning.assert_not_called()

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_no_warning_matching_architectures_x86_64(self, mock_get_host_arch, mock_log):
        """Test no warning when x86_64 host matches x86_64 function."""
        mock_get_host_arch.return_value = X86_64
        function = generate_function(name="TestFunction", architectures=[X86_64])

        warn_cross_architecture_build([function], "docker")

        mock_log.warning.assert_not_called()

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_handles_missing_function_architecture(self, mock_get_host_arch, mock_log):
        """Test handling of functions without explicit architecture (defaults to x86_64)."""
        mock_get_host_arch.return_value = ARM64
        function = generate_function(name="TestFunction", architectures=None)

        warn_cross_architecture_build([function], "finch")

        mock_log.warning.assert_called_once_with(
            "Cross-architecture build detected: Building %s function '%s' on %s host. "
            "This may cause build failures with %s. "
            "Consider updating the function architecture to '%s' in template.yaml",
            X86_64,
            "TestFunction",
            ARM64,
            "finch",
            ARM64,
        )

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_multiple_functions_with_mixed_architectures(self, mock_get_host_arch, mock_log):
        """Test multiple functions with mixed architectures."""
        mock_get_host_arch.return_value = ARM64
        function1 = generate_function(name="Function1", architectures=[X86_64])  # Mismatch
        function2 = generate_function(name="Function2", architectures=[ARM64])  # Match
        function3 = generate_function(name="Function3", architectures=None)  # Mismatch (defaults to x86_64)

        warn_cross_architecture_build([function1, function2, function3], "finch")

        # Should warn for function1 and function3, but not function2
        self.assertEqual(mock_log.warning.call_count, 2)

        # Check first warning call (function1)
        first_call = mock_log.warning.call_args_list[0]
        self.assertEqual(first_call[0][2], "Function1")  # function name is 3rd argument (index 2)
        self.assertEqual(first_call[0][1], X86_64)  # function arch is 2nd argument (index 1)

        # Check second warning call (function3)
        second_call = mock_log.warning.call_args_list[1]
        self.assertEqual(second_call[0][2], "Function3")  # function name is 3rd argument (index 2)
        self.assertEqual(second_call[0][1], X86_64)  # function arch is 2nd argument (index 1)

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_empty_functions_list(self, mock_get_host_arch, mock_log):
        """Test handling of empty functions list."""
        mock_get_host_arch.return_value = ARM64

        warn_cross_architecture_build([], "finch")

        mock_log.warning.assert_not_called()

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_includes_container_runtime_in_warning(self, mock_get_host_arch, mock_log):
        """Test that container runtime is included in warning message."""
        mock_get_host_arch.return_value = ARM64
        function = generate_function(name="TestFunction", architectures=[X86_64])

        warn_cross_architecture_build([function], "custom-runtime")

        # Container runtime is the 5th argument (index 4)
        container_runtime_arg = mock_log.warning.call_args[0][4]
        self.assertEqual(container_runtime_arg, "custom-runtime")

    @patch("samcli.lib.build.utils.LOG")
    @patch("samcli.lib.build.utils._get_host_architecture")
    def test_graceful_handling_when_host_architecture_detection_fails(self, mock_get_host_arch, mock_log):
        """Test graceful handling when host architecture detection fails."""
        mock_get_host_arch.side_effect = Exception("Platform detection failed")
        function = generate_function(name="TestFunction", architectures=[X86_64])

        # Should not raise exception
        try:
            warn_cross_architecture_build([function], "finch")
        except Exception as e:
            self.fail(f"warn_cross_architecture_build raised an exception: {e}")

        # Should not have called warning since host detection failed
        mock_log.warning.assert_not_called()
