import logging
import os
from pathlib import Path
import shutil
from parameterized import parameterized, parameterized_class

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import run_command


LOG = logging.getLogger(__name__)

configs = {
    ".toml": "samconfig/samconfig.toml",
    ".yaml": "samconfig/samconfig.yaml",
    ".json": "samconfig/samconfig.json",
}


class TestSamConfigWithBuild(BuildIntegBase):
    @parameterized.expand(
        [
            (".toml"),
            (".yaml"),
            (".json"),
        ]
    )
    def test_samconfig_works_with_extension(self, extension):
        cmdlist = self.get_command_list(config_file=configs[extension])

        LOG.info("Running Command: %s", cmdlist)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        stdout = str(command_result[1])
        stderr = str(command_result[2])

        self.assertEqual(command_result.process.returncode, 0, "Build should succeed")
        self.assertIn(
            str(Path(extension, self.template)),
            stdout,
            f"Build template should use build_dir from samconfig{extension}",
        )
        self.assertIn("Starting Build use cache", stderr, f"'cache'=true should be set in samconfig{extension}")

    @parameterized.expand(
        [
            (".toml"),
            (".yaml"),
            (".json"),
        ]
    )
    def test_samconfig_parameters_are_overridden(self, extension):
        overrides = {"Runtime": "python3.8"}
        overridden_build_dir = f"{extension}_override"

        cmdlist = self.get_command_list(
            config_file=configs[extension], parameter_overrides=overrides, build_dir=overridden_build_dir
        )

        LOG.info("Running Command: %s", cmdlist)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        stdout = str(command_result[1])
        stderr = str(command_result[2])

        self.assertEqual(command_result.process.returncode, 0, "Build should succeed")
        self.assertNotIn(
            str(Path(extension, self.template)),
            stdout,
            f"Build template should not use build_dir from samconfig{extension}",
        )
        self.assertIn(
            str(Path(overridden_build_dir, self.template)), stdout, f"Build template should use overridden build_dir"
        )
        self.assertIn("Starting Build use cache", stderr, f"'cache'=true should be set in samconfig{extension}")
        self.assertNotIn("python3.9", stderr, f"parameter_overrides runtime should not read from samconfig{extension}")
        self.assertIn(overrides["Runtime"], stderr, "parameter_overrides should use overridden runtime")
        self.assertNotIn("SomeURI", stderr, f"parameter_overrides should not read ANY values from samconfig{extension}")


@parameterized_class(
    [  # Ordered by expected priority
        {"extensions": [".toml", ".yaml", ".json"]},
        {"extensions": [".yaml", ".json"]},
    ]
)
class TestSamConfigExtensionHierarchy(BuildIntegBase):
    testing_wd = Path(os.getcwd(), "tests", "integration")

    @classmethod
    def setUpClass(cls):
        # Bring config files to cwd
        # for extension in path.exists(), f"File samconfig{extension} should have been created in cwd")
        super().setUpClass()

    def setUp(self):
        super().setUp()
        new_template_location = Path(self.working_dir, "template.yaml")
        new_template_location.write_text(Path(self.template_path).read_text())
        for extension in self.extensions:
            config_contents = Path(self.testing_wd, "testdata", "buildcmd", configs[extension]).read_text()
            new_path = Path(self.working_dir, f"samconfig{extension}")
            new_path.write_text(config_contents)
            self.assertTrue(new_path.exists(), f"File samconfig{extension} should have been created in cwd")

    @classmethod
    def tearDownClass(cls):
        # Remove brought config files from cwd
        super().tearDownClass()

    def tearDown(self):
        for extension in self.extensions:
            config_path = Path(self.working_dir, f"samconfig{extension}")
            os.remove(config_path)
        super().tearDown()

    def test_samconfig_pulls_correct_file_if_multiple(self):
        self.template_path = str(Path(self.working_dir, "template.yaml"))
        cmdlist = self.get_command_list(debug=True)
        LOG.info("Running Command: %s", cmdlist)
        command_result = run_command(cmdlist, cwd=self.working_dir)
        stdout = str(command_result[1])

        self.assertEqual(command_result.process.returncode, 0, "Build should succeed")
        self.assertIn(
            f" {self.extensions[0]}",
            stdout,
            f"samconfig{self.extensions[0]} should take priority in current test group",
        )
        for other_extension in self.extensions[1:]:
            self.assertNotIn(
                f" {other_extension}",
                stdout,
                f"samconfig{other_extension} should not be read over another, higher priority extension",
            )
