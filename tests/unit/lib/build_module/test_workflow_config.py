from unittest import TestCase
from parameterized import parameterized

from samcli.lib.build.workflow_config import get_workflow_config, UnsupportedRuntimeException


class Test_get_workflow_config(TestCase):

    @parameterized.expand([
        ("python2.7", ),
        ("python3.6", )
    ])
    def test_must_work_for_python(self, runtime):

        result = get_workflow_config(runtime)
        self.assertEquals(result.language, "python")
        self.assertEquals(result.dependency_manager, "pip")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "requirements.txt")

    @parameterized.expand([
        ("nodejs4.3", ),
        ("nodejs6.10", ),
        ("nodejs8.10", ),
    ])
    def test_must_work_for_nodejs(self, runtime):

        result = get_workflow_config(runtime)
        self.assertEquals(result.language, "nodejs")
        self.assertEquals(result.dependency_manager, "npm")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "package.json")

    @parameterized.expand([
        ("ruby2.5", )
    ])
    def test_must_work_for_ruby(self, runtime):
        result = get_workflow_config(runtime)
        self.assertEquals(result.language, "ruby")
        self.assertEquals(result.dependency_manager, "bundler")
        self.assertEquals(result.application_framework, None)
        self.assertEquals(result.manifest_name, "Gemfile")

    def test_must_raise_for_unsupported_runtimes(self):

        runtime = "foobar"

        with self.assertRaises(UnsupportedRuntimeException) as ctx:
            get_workflow_config(runtime)

        self.assertEquals(str(ctx.exception),
                          "'foobar' runtime is not supported")
