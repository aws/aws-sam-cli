import os
import pathlib
import subprocess
import tempfile
import sys

from unittest import TestCase

TIMEOUT = 3


class TestCopyTerraformBuiltArtifacts(TestCase):
    def setUp(self) -> None:
        self.script_dir = pathlib.Path(__file__).parents[3].joinpath("samcli/hook_packages/terraform")
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
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            str(self.directory),
            "--expression",
            self.expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        with open(self.input_file, "rb") as f:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(0, process.returncode)
        self.assertEqual(os.listdir(self.directory), [self.artifact_name])

    def test_script_output_path_zip(self):
        input_zip_file = self.testdata_directory.joinpath("build-output-path-zip.json")
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            str(self.directory),
            "--expression",
            self.expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        with open(input_zip_file, "rb") as f:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(0, process.returncode)
        self.assertEqual(os.listdir(self.directory), [self.artifact_name])

    def test_script_output_path_directory_invalid_directory(self):
        directory = "not-a-dir"
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            directory,
            "--expression",
            self.expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        with open(self.input_file, "rb") as f:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(1, process.returncode)

    def test_script_output_path_directory_invalid_expression(self):
        expression = (
            '|values|root_module|child_modules|[?address=="module_address"]|resources'
            '?address=="sam_metadata_address"]'
        )
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            f"{str(self.directory)}",
            "--expression",
            expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        with open(self.input_file, "rb") as f:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(1, process.returncode)

    def test_script_output_path_directory_valid_expression_invalid_extracted_path(self):
        expression = (
            '|values|root_module|child_modules|[?address=="module_address"]|resources|['
            '?address=="sam_metadata_address"]|values|triggers'
        )
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            f"{str(self.directory)}",
            "--expression",
            expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        with open(self.input_file, "rb") as f:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(1, process.returncode)

    def test_script_output_path_directory_same_directory_and_extracted_path(self):
        directory = self.testdata_directory.joinpath("output_path_dir")
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            f"{str(directory)}",
            "--expression",
            self.expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        with open(self.input_file, "rb") as f:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(1, process.returncode)

    def test_script_output_path_no_stdin(self):
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            f"{str(self.directory)}",
            "--expression",
            self.expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        try:
            process.communicate(timeout=TIMEOUT)
        except TimeoutError:
            process.kill()
            raise
        self.assertEqual(1, process.returncode)

    def test_script_output_path_invalid_json(self):
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            f"{str(self.directory)}",
            "--expression",
            self.expression,
            "--terraform-project-root",
            f"{str(self.testdata_directory)}",
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        try:
            process.communicate(timeout=TIMEOUT, input=b"invalid_json")
        except TimeoutError:
            process.kill()
            raise
        self.assertEqual(1, process.returncode)

    def test_script_output_path_invalid_terraform_project_root(self):
        command = [
            f"{str(sys.executable)}",
            f"{str(self.script_location)}",
            "--directory",
            f"{str(self.directory)}",
            "--expression",
            self.expression,
            "--terraform-project-root",
            "not-a-dir",
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        with open(self.input_file, "rb") as f:
            try:
                process.communicate(timeout=TIMEOUT, input=f.read())
            except TimeoutError:
                process.kill()
                raise
            self.assertEqual(1, process.returncode)
