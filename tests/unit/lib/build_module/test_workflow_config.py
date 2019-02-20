from unittest import TestCase
from parameterized import parameterized
from mock import patch

from samcli.lib.build.workflow_config import get_workflow_config, UnsupportedRuntimeException


class Test_get_workflow_config(TestCase):

    def setUp(self):
        self.code_dir = ''
        self.project_dir = ''

    @parameterized.expand([
        ("python2.7", ),
        ("python3.6", )
    ])
    def test_must_work_for_python(self, runtime):

        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEquals(result.language, "python")
        self.assertEquals(result.dependency_manager, "pip")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "requirements.txt")
        self.assertIsNone(result.executable_search_paths)

    @parameterized.expand([
        ("nodejs4.3", ),
        ("nodejs6.10", ),
        ("nodejs8.10", ),
    ])
    def test_must_work_for_nodejs(self, runtime):

        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEquals(result.language, "nodejs")
        self.assertEquals(result.dependency_manager, "npm")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "package.json")
        self.assertIsNone(result.executable_search_paths)

    @parameterized.expand([
        ("ruby2.5", )
    ])
    def test_must_work_for_ruby(self, runtime):
        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEquals(result.language, "ruby")
        self.assertEquals(result.dependency_manager, "bundler")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "Gemfile")
        self.assertIsNone(result.executable_search_paths)

    @parameterized.expand([
        ("java8", "build.gradle")
    ])
    @patch("samcli.lib.build.workflow_config.os")
    def test_must_work_for_java(self, runtime, build_file, os_mock):

        os_mock.path.join.side_effect = lambda dirname, v: v
        os_mock.path.exists.side_effect = lambda v: v == build_file

        result = get_workflow_config(runtime, self.code_dir, self.project_dir)
        self.assertEquals(result.language, "java")
        self.assertEquals(result.dependency_manager, "gradle")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "build.gradle")
        self.assertEquals(result.executable_search_paths, [self.code_dir, self.project_dir])

    @parameterized.expand([
        ("java8", "unknown.manifest")
    ])
    @patch("samcli.lib.build.workflow_config.os")
    def test_must_fail_when_manifest_not_found(self, runtime, build_file, os_mock):

        os_mock.path.join.side_effect = lambda dirname, v: v
        os_mock.path.exists.side_effect = lambda v: v == build_file

        with self.assertRaises(UnsupportedRuntimeException) as ctx:
            get_workflow_config(runtime, self.code_dir, self.project_dir)

        self.assertIn("Unable to find a supported build workflow for runtime '{}'.".format(runtime),
                      str(ctx.exception))

    def test_must_raise_for_unsupported_runtimes(self):

        runtime = "foobar"

        with self.assertRaises(UnsupportedRuntimeException) as ctx:
            get_workflow_config(runtime, self.code_dir, self.project_dir)

        self.assertEquals(str(ctx.exception),
                          "'foobar' runtime is not supported")
