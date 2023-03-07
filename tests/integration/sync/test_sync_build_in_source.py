import os
from pathlib import Path
import shutil
import pytest
import logging
import json
from unittest import skip
from parameterized import parameterized, parameterized_class

from tests.integration.sync.sync_integ_base import SyncIntegBase
from tests.integration.sync.test_sync_code import TestSyncCodeBase
from tests.testing_utils import run_command_with_input
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION

LOG = logging.getLogger(__name__)


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
class TestSyncInfra_BuildInSource_Makefile(SyncIntegBase):
    dependency_layer = False

    def setUp(self):
        super().setUp()

        paths = [
            Path("makefile_function_create_new_file", "file-created-from-makefile-function.txt"),
            Path("makefile_layer_create_new_file", "file-created-from-makefile-layer.txt"),
        ]
        self.new_files_in_source = [self.test_data_path.joinpath("code", "before", path) for path in paths]

    def tearDown(self):
        super().tearDown()
        for path in self.new_files_in_source:
            if os.path.isfile(path):
                os.remove(path)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    def test_sync_builds_and_deploys_successfully(self, build_in_source, new_file_should_be_in_source):
        template_path = str(self.test_data_path.joinpath("code", "before", "template-makefile-create-new-file.yaml"))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            stack_name=stack_name,
            dependency_layer=self.dependency_layer,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
            build_in_source=build_in_source,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Sync infra completed.", str(sync_process_execute.stderr))

        # check whether the new files were created in the source directory
        for path in self.new_files_in_source:
            self.assertEqual(os.path.isfile(path), new_file_should_be_in_source)

        stack_resources = self._get_stacks(stack_name)
        lambda_functions = stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(
                lambda_response.get("message"), "function requests version: 2.23.0, layer six version: 1.16.0"
            )


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
class TestSyncCode_BuildInSource_Makefile(TestSyncCodeBase):
    dependency_layer = False
    folder = "code"
    template = "template-makefile-create-new-file.yaml"

    def setUp(self):
        super().setUp()
        paths = [
            Path("makefile_function_create_new_file", "file-created-from-makefile-function.txt"),
            Path("makefile_layer_create_new_file", "file-created-from-makefile-layer.txt"),
        ]
        # When running tests, TestSyncCodeBase copies the source onto a temp directory
        self.new_files_in_source = [TestSyncCodeBase.temp_dir.joinpath(path) for path in paths]

    def tearDown(self):
        super().tearDown()
        for path in self.new_files_in_source:
            if os.path.isfile(path):
                os.remove(path)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    def test_sync_code_builds_and_deploys_successfully(self, build_in_source, new_file_should_be_in_source):
        # update layer to trigger rebuild
        layer_path = "makefile_layer_create_new_file"
        shutil.rmtree(TestSyncCodeBase.temp_dir.joinpath(layer_path), ignore_errors=True)
        shutil.copytree(
            self.test_data_path.joinpath(self.folder).joinpath("after").joinpath(layer_path),
            TestSyncCodeBase.temp_dir.joinpath(layer_path),
        )

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            stack_name=TestSyncCodeBase.stack_name,
            code=True,
            dependency_layer=self.dependency_layer,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            build_in_source=build_in_source,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # check whether the new files were created in the source directory
        for path in self.new_files_in_source:
            self.assertEqual(os.path.isfile(path), new_file_should_be_in_source)

        stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        lambda_functions = stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(
                lambda_response.get("message"), "function requests version: 2.23.0, layer six version: 1.16.0"
            )


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncInfra_BuildInSource_Esbuild(SyncIntegBase):
    def setUp(self):
        super().setUp()
        self.source_dependencies_paths = []

    def tearDown(self):
        super().tearDown()
        # clean up dependencies installed in source directories
        for path in self.source_dependencies_paths:
            shutil.rmtree(path, ignore_errors=True)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    @pytest.mark.flaky(reruns=3)
    def test_sync_builds_successfully_without_local_dependencies(
        self, build_in_source, dependencies_expected_in_source
    ):
        template_path = str(self.test_data_path.joinpath("code", "before", "template-esbuild.yaml"))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        self.source_dependencies_paths = [
            self.test_data_path.joinpath("code", "before", "esbuild_function", "node_modules")
        ]

        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            stack_name=stack_name,
            dependency_layer=self.dependency_layer,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
            build_in_source=build_in_source,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Sync infra completed.", str(sync_process_execute.stderr))

        # check whether dependencies were installed in the source directory
        for path in self.source_dependencies_paths:
            self.assertEqual(os.path.isdir(path), dependencies_expected_in_source)

        stack_resources = self._get_stacks(stack_name)
        lambda_functions = stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")

    @pytest.mark.flaky(reruns=3)
    def test_sync_builds_successfully_with_local_dependency(self):
        template_path = str(self.test_data_path.joinpath("code", "before", "template-esbuild.yaml"))
        stack_name = self._method_to_stack_name(self.id())
        self.stacks.append({"name": stack_name})

        codeuri = "esbuild_function_with_local_dependency"
        self.source_dependencies_paths = [self.test_data_path.joinpath("code", "before", codeuri, "node_modules")]

        sync_command_list = self.get_sync_command_list(
            template_file=template_path,
            stack_name=stack_name,
            dependency_layer=self.dependency_layer,
            parameter_overrides=f"Parameter=Clarity CodeUri={codeuri}",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            capabilities_list=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
            tags="integ=true clarity=yes foo_bar=baz",
            build_in_source=True,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)
        self.assertIn("Sync infra completed.", str(sync_process_execute.stderr))

        # check whether dependencies were installed in the source directory
        for path in self.source_dependencies_paths:
            self.assertEqual(os.path.isdir(path), True)

        stack_resources = self._get_stacks(stack_name)
        lambda_functions = stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")


@skip("Building in source option is not exposed yet. Stop skipping once it is.")
@parameterized_class([{"dependency_layer": True}, {"dependency_layer": False}])
class TestSyncCode_BuildInSource_Esbuild(TestSyncCodeBase):
    dependency_layer = False
    folder = "code"
    template = "template-esbuild.yaml"

    def setUp(self):
        super().setUp()
        self.source_dependencies_paths = []

    def tearDown(self):
        super().tearDown()
        # clean up dependencies installed in source directories
        for path in self.source_dependencies_paths:
            shutil.rmtree(path, ignore_errors=True)

    @parameterized.expand(
        [
            (True, True),  # build in source
            (False, False),  # don't build in source
            (None, False),  # use default for workflow (don't build in source)
        ]
    )
    def test_sync_code_builds_successfully_without_local_dependencies(
        self, build_in_source, dependencies_expected_in_source
    ):
        self.source_dependencies_paths = [TestSyncCodeBase.temp_dir.joinpath("esbuild_function", "node_modules")]

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            stack_name=TestSyncCodeBase.stack_name,
            code=True,
            dependency_layer=self.dependency_layer,
            parameter_overrides="Parameter=Clarity",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            build_in_source=build_in_source,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # check whether dependencies were installed in the source directory
        for path in self.source_dependencies_paths:
            self.assertEqual(os.path.isdir(path), dependencies_expected_in_source)

        stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        lambda_functions = stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")

    def test_sync_code_builds_successfully_with_local_dependencies(self):
        codeuri = "esbuild_function_with_local_dependency"
        self.source_dependencies_paths = [TestSyncCodeBase.temp_dir.joinpath(codeuri, "node_modules")]

        # Run code sync
        sync_command_list = self.get_sync_command_list(
            template_file=TestSyncCodeBase.template_path,
            stack_name=TestSyncCodeBase.stack_name,
            code=True,
            dependency_layer=self.dependency_layer,
            parameter_overrides=f"Parameter=Clarity CodeUri={codeuri}",
            image_repository=self.ecr_repo_name,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key,
            tags="integ=true clarity=yes foo_bar=baz",
            build_in_source=True,
        )
        sync_process_execute = run_command_with_input(sync_command_list, "y\n".encode())
        self.assertEqual(sync_process_execute.process.returncode, 0)

        # check whether dependencies were installed in the source directory
        for path in self.source_dependencies_paths:
            self.assertEqual(os.path.isdir(path), True)

        stack_resources = self._get_stacks(TestSyncCodeBase.stack_name)
        lambda_functions = stack_resources.get(AWS_LAMBDA_FUNCTION)
        for lambda_function in lambda_functions:
            lambda_response = json.loads(self._get_lambda_response(lambda_function))
            self.assertEqual(lambda_response.get("message"), "hello world")
