import os
from pathlib import Path
import pytest
import logging
from parameterized import parameterized
from samcli.lib.utils import osutils

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

    def setUp(self):
        super().setUp()

        self.code_uri = "provided_create_new_file"
        test_data_code_uri = Path(self.test_data_path, self.code_uri)
        self.file_created_from_make_command = "file-created-from-make-command.txt"

        scratch_code_uri_path = Path(self.working_dir, self.code_uri)
        self.code_uri_path = str(scratch_code_uri_path)

        # copy source code into temporary directory and update code uri to that scratch dir
        osutils.copytree(test_data_code_uri, scratch_code_uri_path)

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
            code_uri=self.code_uri_path,
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

        source_files_path = Path(self.test_data_path, "Esbuild")
        osutils.copytree(source_files_path, self.working_dir)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, dependencies_expected_in_source):
        codeuri = os.path.join(self.working_dir, "Node")

        self._test_with_default_package_json(
            build_in_source=build_in_source,
            runtime="nodejs18.x",
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
        codeuri = os.path.join(self.working_dir, "NodeWithLocalDependency")
        runtime = "nodejs18.x"
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

        osutils.copytree(Path(self.test_data_path, "Esbuild"), self.working_dir)

    def tearDown(self):
        super().tearDown()

    def validate_node_modules(self, is_build_in_source_behaviour: bool):
        # validate if node modules exist in the built artifact dir
        built_node_modules = Path(self.default_build_dir, "Function", "node_modules")
        self.assertEqual(built_node_modules.is_dir(), True, "node_modules not found in artifact dir")
        self.assertEqual(built_node_modules.is_symlink(), is_build_in_source_behaviour)

        # validate that node modules are suppose to exist in the source dir
        source_node_modules = Path(self.codeuri_path, "node_modules")
        self.assertEqual(source_node_modules.is_dir(), is_build_in_source_behaviour)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_without_local_dependencies(self, build_in_source, expected_built_in_source):
        self.codeuri_path = Path(self.working_dir, "Node")

        overrides = self.get_override(
            runtime="nodejs18.x", code_uri=self.codeuri_path, architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=build_in_source, parameter_overrides=overrides, debug=True)

        run_command(command_list, self.working_dir)
        self.validate_node_modules(expected_built_in_source)

    @pytest.mark.flaky(reruns=3)
    def test_builds_successfully_with_local_dependency(self):
        self.codeuri_path = Path(self.working_dir, "NodeWithLocalDependency")

        overrides = self.get_override(
            runtime="nodejs18.x", code_uri=self.codeuri_path, architecture="x86_64", handler="main.lambdaHandler"
        )
        command_list = self.get_command_list(build_in_source=True, parameter_overrides=overrides)

        run_command(command_list, self.working_dir)
        self.validate_node_modules(True)
