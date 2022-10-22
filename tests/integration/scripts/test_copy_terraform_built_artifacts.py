import os
import pathlib
import subprocess
import tempfile
import sys

from unittest import TestCase

TIMEOUT = 3


class TestCopyTerraformBuiltArtifacts(TestCase):
    def setUp(self) -> None:
        self.script_dir = pathlib.Path(__file__).parents[3].joinpath("samcli", "hook_packages", "terraform")
        self.working_dir = pathlib.Path(__file__).parents[0]
        self.script_name = "copy_terraform_built_artifacts.py"
        self.script_location = self.script_dir.joinpath(self.script_name)
        self.testdata_directory = pathlib.Path(__file__).parent.joinpath("testdata")
        self.input_file = self.testdata_directory.joinpath("build-output-path-dir.json")
        self.expression = (
            '|values|root_module|child_modules|[?address=="module_address"]|resources|['
            '?address=="sam_metadata_address"]|values|triggers|built_output_path'
        )
        self.directory = pathlib.Path(tempfile.mkdtemp()).absolute()
        self.artifact_name = "test_artifact"

    def test_script_output_path_directory(self):
        with open(self.input_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                str(self.directory),
                "--expression",
                self.expression,
                "--json",
                json_str,
            ]
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )
        self.assertEqual(os.listdir(self.directory), [self.artifact_name])

    def test_script_output_path_zip(self):
        input_zip_file = self.testdata_directory.joinpath("build-output-path-zip.json")
        with open(input_zip_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                str(self.directory),
                "--expression",
                self.expression,
                "--json",
                json_str,
            ]
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )
        self.assertEqual(os.listdir(self.directory), [self.artifact_name])

    def test_script_output_path_directory_invalid_directory(self):
        directory = "not-a-dir"
        with open(self.input_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                directory,
                "--expression",
                self.expression,
                "--json",
                json_str,
            ]
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )

    def test_script_output_path_directory_invalid_expression(self):
        expression = (
            '|values|root_module|child_modules|[?address=="module_address"]|resources'
            '?address=="sam_metadata_address"]'
        )
        with open(self.input_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                f"{str(self.directory)}",
                "--expression",
                expression,
                "--json",
                json_str,
            ]
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )

    def test_script_output_path_directory_valid_expression_invalid_extracted_path(self):
        expression = (
            '|values|root_module|child_modules|[?address=="module_address"]|resources|['
            '?address=="sam_metadata_address"]|values|triggers'
        )
        with open(self.input_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                f"{str(self.directory)}",
                "--expression",
                expression,
                "--json",
                json_str,
            ]
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )

    def test_script_output_path_directory_same_directory_and_extracted_path(self):
        directory = self.testdata_directory.joinpath("output_path_dir")
        with open(self.input_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                f"{str(directory)}",
                "--expression",
                self.expression,
                "--json",
                json_str,
            ]
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )

    def test_script_output_path_no_target_and_no_json(self):
        with self.assertRaises(subprocess.CalledProcessError):
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                f"{str(self.directory)}",
                "--expression",
                self.expression,
            ]
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )

    def test_script_output_path_both_target_and_option(self):
        with open(self.input_file, "rb") as f:
            json_str = f.read().decode("utf-8")
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                f"{str(self.directory)}",
                "--expression",
                self.expression,
                "--json",
                json_str,
                "--target",
                "resource.path",
            ]
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )

    def test_script_output_path_invalid_json(self):
        with self.assertRaises(subprocess.CalledProcessError):
            command = [
                f"{str(sys.executable)}",
                f"{str(self.script_location)}",
                "--directory",
                f"{str(self.directory)}",
                "--expression",
                self.expression,
                "--json",
                "invalid_json",
            ]
            subprocess.check_call(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE, cwd=self.working_dir
            )
