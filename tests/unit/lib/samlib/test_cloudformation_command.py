"""
Tests Deploy  CLI
"""

import os
from subprocess import CalledProcessError, PIPE

from unittest import TestCase
from unittest.mock import patch, call, ANY

from samcli.lib.samlib.cloudformation_command import execute_command, find_executable


class TestExecuteCommand(TestCase):
    def setUp(self):
        self.args = ("--arg1", "value1", "different args", "more")

    @patch("subprocess.check_call")
    @patch("samcli.lib.samlib.cloudformation_command.find_executable")
    def test_must_add_template_file(self, find_executable_mock, check_call_mock):
        find_executable_mock.return_value = "mycmd"
        check_call_mock.return_value = True
        execute_command("command", self.args, "/path/to/template")

        check_call_mock.assert_called_with(
            ["mycmd", "cloudformation", "command"]
            + ["--arg1", "value1", "different args", "more", "--template-file", "/path/to/template"],
            env=ANY,
        )

    @patch("subprocess.check_call")
    @patch("samcli.lib.samlib.cloudformation_command.find_executable")
    @patch("samcli.lib.samlib.cloudformation_command.GlobalConfig")
    def test_must_add_sam_cli_info_to_execution_env_var_if_telemetry_is_on(
        self, global_config_mock, find_executable_mock, check_call_mock
    ):
        installation_id = "testtest"
        global_config_mock.return_value.installation_id = installation_id
        global_config_mock.return_value.telemetry_enabled = True

        expected_env = os.environ.copy()
        expected_env["AWS_EXECUTION_ENV"] = "SAM-" + installation_id

        find_executable_mock.return_value = "mycmd"
        check_call_mock.return_value = True
        execute_command("command", self.args, "/path/to/template")

        check_call_mock.assert_called()
        kwargs = check_call_mock.call_args[1]
        self.assertIn("env", kwargs)
        self.assertEqual(kwargs["env"], expected_env)

    @patch("subprocess.check_call")
    @patch("samcli.lib.samlib.cloudformation_command.find_executable")
    @patch("samcli.lib.samlib.cloudformation_command.GlobalConfig")
    def test_must_not_set_exec_env(self, global_config_mock, find_executable_mock, check_call_mock):
        global_config_mock.return_value.telemetry_enabled = False

        # Expected to pass just a copy of the environment variables without modification
        expected_env = os.environ.copy()

        find_executable_mock.return_value = "mycmd"
        check_call_mock.return_value = True
        execute_command("command", self.args, "/path/to/template")

        check_call_mock.assert_called()
        kwargs = check_call_mock.call_args[1]
        self.assertIn("env", kwargs)
        self.assertEqual(kwargs["env"], expected_env)

    @patch("sys.exit")
    @patch("subprocess.check_call")
    @patch("samcli.lib.samlib.cloudformation_command.find_executable")
    def test_command_must_exit_with_status_code(self, find_executable_mock, check_call_mock, exit_mock):
        find_executable_mock.return_value = "mycmd"
        check_call_mock.side_effect = CalledProcessError(2, "Error")
        exit_mock.return_value = True
        execute_command("command", self.args, None)
        exit_mock.assert_called_with(2)


class TestFindExecutable(TestCase):
    @patch("subprocess.Popen")
    @patch("platform.system")
    def test_must_use_raw_name(self, platform_system_mock, popen_mock):
        platform_system_mock.return_value = "Linux"
        execname = "foo"

        find_executable(execname)

        self.assertEqual(popen_mock.mock_calls, [call([execname], stdout=PIPE, stderr=PIPE)])

    @patch("subprocess.Popen")
    @patch("platform.system")
    def test_must_use_name_with_cmd_extension_on_windows(self, platform_system_mock, popen_mock):
        platform_system_mock.return_value = "windows"
        execname = "foo"
        expected = "foo.cmd"

        result = find_executable(execname)
        self.assertEqual(result, expected)

        self.assertEqual(popen_mock.mock_calls, [call(["foo.cmd"], stdout=PIPE, stderr=PIPE)])

    @patch("subprocess.Popen")
    @patch("platform.system")
    def test_must_use_name_with_exe_extension_on_windows(self, platform_system_mock, popen_mock):
        platform_system_mock.return_value = "windows"
        execname = "foo"
        expected = "foo.exe"

        popen_mock.side_effect = [OSError, "success"]  # fail on .cmd extension

        result = find_executable(execname)
        self.assertEqual(result, expected)

        self.assertEqual(
            popen_mock.mock_calls,
            [call(["foo.cmd"], stdout=PIPE, stderr=PIPE), call(["foo.exe"], stdout=PIPE, stderr=PIPE)],
        )

    @patch("subprocess.Popen")
    @patch("platform.system")
    def test_must_use_name_with_no_extension_on_windows(self, platform_system_mock, popen_mock):
        platform_system_mock.return_value = "windows"
        execname = "foo"
        expected = "foo"

        popen_mock.side_effect = [OSError, OSError, "success"]  # fail on .cmd and .exe extension

        result = find_executable(execname)
        self.assertEqual(result, expected)

        self.assertEqual(
            popen_mock.mock_calls,
            [
                call(["foo.cmd"], stdout=PIPE, stderr=PIPE),
                call(["foo.exe"], stdout=PIPE, stderr=PIPE),
                call(["foo"], stdout=PIPE, stderr=PIPE),
            ],
        )

    @patch("subprocess.Popen")
    @patch("platform.system")
    def test_must_raise_error_if_executable_not_found(self, platform_system_mock, popen_mock):
        platform_system_mock.return_value = "windows"
        execname = "foo"

        popen_mock.side_effect = [OSError, OSError, OSError, "success"]  # fail on all executable names

        with self.assertRaises(OSError) as ctx:
            find_executable(execname)

        expected = "Cannot find AWS CLI installation, was looking at executables with names: {}".format(
            ["foo.cmd", "foo.exe", "foo"]
        )
        self.assertEqual(expected, str(ctx.exception))

        self.assertEqual(
            popen_mock.mock_calls,
            [
                call(["foo.cmd"], stdout=PIPE, stderr=PIPE),
                call(["foo.exe"], stdout=PIPE, stderr=PIPE),
                call(["foo"], stdout=PIPE, stderr=PIPE),
            ],
        )
