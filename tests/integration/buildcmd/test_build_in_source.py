import os
from pathlib import Path
import shutil
import pytest
import logging
from parameterized import parameterized

from tests.integration.buildcmd.build_integ_base import (
    BuildIntegNodeBase,
    BuildIntegProvidedBase,
    BuildIntegEsbuildBase,
)
from tests.testing_utils import run_command

LOG = logging.getLogger(__name__)


class TestBuildCommand_BuildInSource_Makefile(BuildIntegProvidedBase):
    template = "template.yaml"
    is_nested_parent = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code_uri = "provided_create_new_file"
        cls.code_uri_path = os.path.join(cls.test_data_path, cls.code_uri)
        cls.file_created_from_make_command = "file-created-from-make-command.txt"

    def tearDown(self):
        super().tearDown()
        new_file_in_codeuri_path = os.path.join(self.code_uri_path, self.file_created_from_make_command)
        if os.path.isfile(new_file_in_codeuri_path):
            os.remove(new_file_in_codeuri_path)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_makefile(self, build_in_source, new_file_should_be_in_codeuri):
        self._test_with_Makefile(
            runtime="provided.al2",
            use_container=False,
            manifest=None,
            code_uri=self.code_uri,
            build_in_source=build_in_source,
        )

        self.assertEqual(
            self.file_created_from_make_command in os.listdir(self.code_uri_path), new_file_should_be_in_codeuri
        )


class TestBuildCommand_BuildInSource_Esbuild(BuildIntegEsbuildBase):
    is_nested_parent = False
    template = "template_with_metadata_esbuild.yaml"

    def setUp(self):
        super().setUp()
        self.source_directories = []

    def tearDown(self):
        super().tearDown()
        # clean up dependencies installed in source directories
        for source in self.source_directories:
            shutil.rmtree(os.path.join(source, "node_modules"), ignore_errors=True)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, dependencies_expected_in_source):
        codeuri = os.path.join(self.test_data_path, "Esbuild", "Node")
        self.source_directories = [codeuri]

        self._test_with_default_package_json(
            build_in_source=build_in_source,
            runtime="nodejs16.x",
            code_uri=codeuri,
            handler="main.lambdaHandler",
            architecture="x86_64",
            use_container=False,
            expected_files={"main.js", "main.js.map"},
        )

        # check whether dependencies were installed in source dir
        self.assertEqual(os.path.isdir(os.path.join(codeuri, "node_modules")), dependencies_expected_in_source)

    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_local_dependency(self):
        codeuri = os.path.join(self.test_data_path, "Esbuild", "NodeWithLocalDependency")
        self.source_directories = [codeuri]
        runtime = "nodejs16.x"
        architecture = "x86_64"

        self._test_with_default_package_json(
            build_in_source=True,
            runtime=runtime,
            code_uri=codeuri,
            handler="main.lambdaHandler",
            architecture=architecture,
            use_container=False,
            expected_files={"main.js", "main.js.map"},
        )

        # check whether dependencies were installed in source dir
        self.assertEqual(os.path.isdir(os.path.join(codeuri, "node_modules")), True)


class TestBuildCommand_BuildInSource_Nodejs(BuildIntegNodeBase):
    is_nested_parent = False
    template = "template.yaml"

    def setUp(self):
        super().setUp()
        self.source_directories = []

    def tearDown(self):
        super().tearDown()
        # clean up dependencies installed in source directories
        for source in self.source_directories:
            shutil.rmtree(Path(source, "node_modules"), ignore_errors=True)

    def validate_node_modules_folder(self, expected_result: bool):
        source_node_modules = Path(self.codeuri_path, "node_modules")

        self.assertEqual(source_node_modules.is_dir(), expected_result, "node_modules not found in source folder")

    def validate_node_modules_linked(self):
        built_node_modules = Path(self.default_build_dir, "Function", "node_modules")

        self.assertEqual(built_node_modules.is_dir(), True, "node_modules not found in artifact folder")
        self.assertEqual(built_node_modules.is_symlink(), True, "node_modules not a symlink in artifact folder")

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    # @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, dependencies_expected_in_source):
        self.codeuri_path = Path(self.test_data_path, "Node")
        self.source_directories = [str(self.codeuri_path)]

        overrides = self.get_override(
            runtime="nodejs16.x", code_uri=self.CODE_URI, architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=build_in_source, parameter_overrides=overrides)

        run_command(command_list, self.working_dir)

        # check whether dependencies were installed in source dir
        self.validate_node_modules_folder(dependencies_expected_in_source)

    # @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_local_dependency(self):
        codeuri_folder = Path("Esbuild", "NodeWithLocalDependency")

        self.codeuri_path = Path(self.test_data_path, codeuri_folder)
        self.CODE_URI = str(codeuri_folder)

        self.source_directories = [str(self.codeuri_path)]

        overrides = self.get_override(
            runtime="nodejs16.x", code_uri=self.CODE_URI, architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=True, parameter_overrides=overrides)

        run_command(command_list, self.working_dir)

        # check whether dependencies were installed in source dir
        self.validate_node_modules_folder(True)
        self.validate_node_modules_linked()