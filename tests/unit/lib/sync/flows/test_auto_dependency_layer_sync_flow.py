import os.path
from unittest import TestCase
from unittest.mock import Mock, patch, ANY

from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.sync.exceptions import MissingFunctionBuildDefinition, InvalidRuntimeDefinitionForFunction
from samcli.lib.sync.flows.auto_dependency_layer_sync_flow import (
    AutoDependencyLayerParentSyncFlow,
    AutoDependencyLayerSyncFlow,
)
from samcli.lib.sync.flows.layer_sync_flow import FunctionLayerReferenceSync


class TestAutoDependencyLayerParentSyncFlow(TestCase):
    def setUp(self) -> None:
        self.sync_flow = AutoDependencyLayerParentSyncFlow(
            "function_identifier", Mock(), Mock(stack_name="stack_name"), Mock(), [Mock()]
        )

    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.super")
    def test_gather_dependencies(self, patched_super):
        patched_super.return_value.gather_dependencies.return_value = []

        dependencies = self.sync_flow.gather_dependencies()
        self.assertEqual(len(dependencies), 1)
        self.assertIsInstance(dependencies[0], AutoDependencyLayerSyncFlow)

    def test_combine_dependencies(self):
        self.assertFalse(self.sync_flow._combine_dependencies())


class TestAutoDependencyLayerSyncFlow(TestCase):
    def setUp(self) -> None:
        self.build_graph = Mock(spec=BuildGraph)
        self.stack_name = "stack_name"
        self.build_dir = "build_dir"
        self.function_identifier = "function_identifier"
        self.sync_flow = AutoDependencyLayerSyncFlow(
            self.function_identifier,
            self.build_graph,
            Mock(build_dir=self.build_dir),
            Mock(stack_name=self.stack_name),
            Mock(),
            [Mock()],
        )

    def test_gather_resources_fail_when_no_function_build_definition_found(self):
        self.build_graph.get_function_build_definitions.return_value = []
        with self.assertRaises(MissingFunctionBuildDefinition):
            self.sync_flow.gather_resources()

    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.SamFunctionProvider")
    def test_gather_resources_fail_when_no_runtime_defined_for_function(self, patched_function_provider):
        self.build_graph.get_function_build_definitions.return_value = [Mock()]
        patched_function_provider.return_value.get.return_value = Mock(runtime=None)
        with self.assertRaises(InvalidRuntimeDefinitionForFunction):
            self.sync_flow.gather_resources()

    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.uuid")
    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.file_checksum")
    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.make_zip")
    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.tempfile")
    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.NestedStackManager")
    def test_gather_resources(
        self,
        patched_nested_stack_manager,
        patched_tempfile,
        patched_make_zip,
        patched_file_checksum,
        patched_uuid,
    ):
        dependencies_dir = "dependencies_dir"
        tmpdir = "tmpdir"
        uuid_hex = "uuid_hex"
        runtime = "runtime"
        zipfile = "zipfile"

        patched_tempfile.gettempdir.return_value = tmpdir
        patched_uuid.uuid4.return_value = Mock(hex=uuid_hex)
        patched_make_zip.return_value = zipfile
        self.build_graph.get_function_build_definitions.return_value = [Mock(dependencies_dir=dependencies_dir)]

        with patch.object(self.sync_flow, "_get_compatible_runtimes") as patched_comp_runtimes:
            patched_comp_runtimes.return_value = [runtime]
            self.sync_flow.gather_resources()

            patched_nested_stack_manager.update_layer_folder.assert_called_with(
                "build_dir", dependencies_dir, ANY, self.function_identifier, runtime
            )
            patched_make_zip.assert_called_with(
                os.path.join(tmpdir, f"data-{uuid_hex}"), self.sync_flow._artifact_folder
            )
            patched_file_checksum.assert_called_with(zipfile, ANY)

    def test_empty_gather_dependencies(self):
        with patch.object(self.sync_flow, "_get_dependent_functions") as patched_get_dependent_functions:
            patched_get_dependent_functions.return_value = []
            self.assertEqual(self.sync_flow.gather_dependencies(), [])

    def test_gather_dependencies(self):
        layer_identifier = "layer_identifier"
        self.sync_flow._layer_identifier = layer_identifier
        with patch.object(self.sync_flow, "_get_dependent_functions") as patched_get_dependent_functions:
            patched_get_dependent_functions.return_value = [
                Mock(layers=[Mock(full_path=layer_identifier)], full_path="Function")
            ]
            dependencies = self.sync_flow.gather_dependencies()
            self.assertEqual(len(dependencies), 1)
            self.assertIsInstance(dependencies[0], FunctionLayerReferenceSync)

    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.SamFunctionProvider")
    def test_get_dependent_functions(self, patched_function_provider):
        given_function_in_template = Mock()
        patched_function_provider.return_value.get.return_value = given_function_in_template

        self.assertEqual(self.sync_flow._get_dependent_functions(), [given_function_in_template])

    @patch("samcli.lib.sync.flows.auto_dependency_layer_sync_flow.SamFunctionProvider")
    def test_get_compatible_runtimes(self, patched_function_provider):
        given_runtime = "python3.9"
        given_function_in_template = Mock(runtime=given_runtime)
        patched_function_provider.return_value.get.return_value = given_function_in_template

        self.assertEqual(self.sync_flow._get_compatible_runtimes(), [given_runtime])
