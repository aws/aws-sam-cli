from unittest import TestCase
from parameterized import parameterized
from unittest.mock import patch

from samcli.lib.build.workflow_config import (
    get_workflow_config,
    UnsupportedRuntimeException,
    UnsupportedBuilderException,
)
from samcli.lib.telemetry.event import Event, EventTracker


class Test_get_workflow_config(TestCase):
    def setUp(self):
        self.code_dir = ""
        self.project_dir = ""
        EventTracker.clear_trackers()

    @parameterized.expand([("python3.7",), ("python3.8",)])
    def test_must_work_for_python(self, runtime):

        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEqual(result.language, "python")
        self.assertEqual(result.dependency_manager, "pip")
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, "requirements.txt")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "python-pip"), EventTracker.get_tracked_events())

    @parameterized.expand([("nodejs12.x",), ("nodejs14.x",), ("nodejs16.x",), ("nodejs18.x",)])
    def test_must_work_for_nodejs(self, runtime):

        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEqual(result.language, "nodejs")
        self.assertEqual(result.dependency_manager, "npm")
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, "package.json")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "nodejs-npm"), EventTracker.get_tracked_events())

    @parameterized.expand([("provided",)])
    def test_must_work_for_provided(self, runtime):
        result = get_workflow_config(runtime, self.code_dir, self.project_dir, specified_workflow="makefile")
        self.assertEqual(result.language, "provided")
        self.assertEqual(result.dependency_manager, None)
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, "Makefile")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "provided-None"), EventTracker.get_tracked_events())

    @parameterized.expand([("provided.al2",)])
    def test_must_work_for_provided_with_build_method_dotnet7(self, runtime):
        result = get_workflow_config(runtime, self.code_dir, self.project_dir, specified_workflow="dotnet7")
        self.assertEqual(result.language, "dotnet")
        self.assertEqual(result.dependency_manager, "cli-package")
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, ".csproj")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "dotnet-cli-package"), EventTracker.get_tracked_events())

    @parameterized.expand([("provided.al2",)])
    def test_must_work_for_provided_with_build_method_rustcargolambda(self, runtime):
        result = get_workflow_config(runtime, self.code_dir, self.project_dir, specified_workflow="rust-cargolambda")
        self.assertEqual(result.language, "rust")
        self.assertEqual(result.dependency_manager, "cargo")
        self.assertIsNone(result.application_framework)
        self.assertEqual(result.manifest_name, "Cargo.toml")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "rust-cargo"), EventTracker.get_tracked_events())

    @parameterized.expand([("provided",)])
    def test_must_work_for_provided_with_no_specified_workflow(self, runtime):
        # Implicitly look for makefile capability.
        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEqual(result.language, "provided")
        self.assertEqual(result.dependency_manager, None)
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, "Makefile")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "provided-None"), EventTracker.get_tracked_events())

    @parameterized.expand([("provided",)])
    def test_raise_exception_for_bad_specified_workflow(self, runtime):
        with self.assertRaises(UnsupportedBuilderException):
            get_workflow_config(runtime, self.code_dir, self.project_dir, specified_workflow="Wrong")

    @parameterized.expand([("ruby2.7",)])
    def test_must_work_for_ruby(self, runtime):
        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEqual(result.language, "ruby")
        self.assertEqual(result.dependency_manager, "bundler")
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, "Gemfile")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "ruby-bundler"), EventTracker.get_tracked_events())

    @parameterized.expand(
        [("java8", "build.gradle", "gradle"), ("java8", "build.gradle.kts", "gradle"), ("java8", "pom.xml", "maven")]
    )
    @patch("samcli.lib.build.workflow_config.os")
    def test_must_work_for_java(self, runtime, build_file, dep_manager, os_mock):
        os_mock.path.join.side_effect = lambda dirname, v: v
        os_mock.path.exists.side_effect = lambda v: v == build_file

        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEqual(result.language, "java")
        self.assertEqual(result.dependency_manager, dep_manager)
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, build_file)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)

        if dep_manager == "gradle":
            self.assertEqual(result.executable_search_paths, [self.code_dir, self.project_dir])
            self.assertIn(Event("BuildWorkflowUsed", "java-gradle"), EventTracker.get_tracked_events())
        else:
            self.assertIsNone(result.executable_search_paths)
            self.assertIn(Event("BuildWorkflowUsed", "java-maven"), EventTracker.get_tracked_events())

    def test_must_get_workflow_for_esbuild(self):
        runtime = "nodejs12.x"
        result = get_workflow_config(runtime, self.code_dir, self.project_dir, specified_workflow="esbuild")
        self.assertEqual(result.language, "nodejs")
        self.assertEqual(result.dependency_manager, "npm-esbuild")
        self.assertEqual(result.application_framework, None)
        self.assertEqual(result.manifest_name, "package.json")
        self.assertIsNone(result.executable_search_paths)
        self.assertEqual(len(EventTracker.get_tracked_events()), 1)
        self.assertIn(Event("BuildWorkflowUsed", "nodejs-npm-esbuild"), EventTracker.get_tracked_events())

    @parameterized.expand([("java8", "unknown.manifest")])
    @patch("samcli.lib.build.workflow_config.os")
    def test_must_fail_when_manifest_not_found(self, runtime, build_file, os_mock):

        os_mock.path.join.side_effect = lambda dirname, v: v
        os_mock.path.exists.side_effect = lambda v: v == build_file

        with self.assertRaises(UnsupportedRuntimeException) as ctx:
            get_workflow_config(runtime, self.code_dir, self.project_dir)

        self.assertIn("Unable to find a supported build workflow for runtime '{}'.".format(runtime), str(ctx.exception))

    def test_must_raise_for_unsupported_runtimes(self):

        runtime = "foobar"

        with self.assertRaises(UnsupportedRuntimeException) as ctx:
            get_workflow_config(runtime, self.code_dir, self.project_dir)

        self.assertEqual(str(ctx.exception), "'foobar' runtime is not supported")
