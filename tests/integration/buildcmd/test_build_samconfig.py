import os
from pathlib import Path
from parameterized import parameterized, parameterized_class
from samcli.lib.config.samconfig import SamConfig

from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import run_command


configs = {
    ".toml": "samconfig/samconfig.toml",
    ".yaml": "samconfig/samconfig.yaml",
    ".yml": "samconfig/samconfig.yml",
    ".json": "samconfig/samconfig.json",
    ".jpeg": "samconfig/samconfig.jpeg",  # unsupported format, but file that exists
}


class TestSamConfigWithBuild(BuildIntegBase):
    @parameterized.expand(
        [
            (".toml"),
            (".yaml"),
            # (".json"),
        ]
    )
    def test_samconfig_works_with_extension(self, extension):
        cmdlist = self.get_command_list(config_file=configs[extension])

        command_result = run_command(cmdlist, cwd=self.working_dir)
        stdout = str(command_result[1])
        stderr = str(command_result[2])

        self.assertEqual(command_result.process.returncode, 0, "Build should succeed")
        self.assertIn(
            f"Built Artifacts  : {extension}",
            stdout,
            f"Build template should use build_dir from samconfig{extension}",
        )
        self.assertIn("Starting Build use cache", stderr, f"'cache'=true should be set in samconfig{extension}")

    def test_samconfig_fails_properly_with_incorrect_extension(self):
        cmdlist = self.get_command_list(config_file=configs[".jpeg"])

        command_result = run_command(cmdlist, cwd=self.working_dir)
        stderr = str(command_result[2])

        self.assertNotEqual(command_result.process.returncode, 0, "Build should not succeed")
        self.assertEqual(command_result.process.returncode, 1, "Correct error code should be thrown")
        self.assertNotIn("Traceback", stderr, "Traceback should not be in output")

    @parameterized.expand(
        [
            (".toml"),
            (".yaml"),
            # (".json"),
        ]
    )
    def test_samconfig_parameters_are_overridden(self, extension):
        overrides = {"Runtime": "python3.8"}
        overridden_build_dir = f"override_{extension}"

        cmdlist = self.get_command_list(
            config_file=configs[extension], parameter_overrides=overrides, build_dir=overridden_build_dir
        )

        command_result = run_command(cmdlist, cwd=self.working_dir)
        stdout = str(command_result[1])
        stderr = str(command_result[2])

        self.assertEqual(command_result.process.returncode, 0, "Build should succeed")
        self.assertNotIn(
            f"Built Artifacts  : {extension}",
            stdout,
            f"Build template should not use build_dir from samconfig{extension}",
        )
        self.assertIn(
            f"Built Artifacts  : {overridden_build_dir}", stdout, f"Build template should use overridden build_dir"
        )
        self.assertIn("Starting Build use cache", stderr, f"'cache'=true should be set in samconfig{extension}")
        self.assertNotIn("python3.9", stderr, f"parameter_overrides runtime should not read from samconfig{extension}")
        self.assertIn(overrides["Runtime"], stderr, "parameter_overrides should use overridden runtime")
        self.assertNotIn("SomeURI", stderr, f"parameter_overrides should not read ANY values from samconfig{extension}")

    def test_save_params_saves_params(self):
        # setup temp dir
        new_template_location = Path(self.working_dir, "template.yaml")
        new_template_location.write_text(Path(self.template_path).read_text())
        config_contents = Path(self.test_data_path, configs[".toml"]).read_text()
        new_config_path = Path(self.working_dir, "samconfig.toml")
        new_config_path.write_text(config_contents)
        self.assertTrue(new_config_path.exists(), "File samconfig.toml should have been created in cwd")

        # do the test
        self.template_path = str(Path(self.working_dir, "template.yaml"))
        cmdlist = self.get_command_list(
            config_file=str(new_config_path), save_params=True, build_dir="new_dir", parallel=True
        )
        command_result = run_command(cmdlist, cwd=self.working_dir)
        stdout = str(command_result[1])

        self.assertEqual(command_result.process.returncode, 0, "Build should succeed")
        self.assertIn(
            f"Built Artifacts  : new_dir",
            stdout,
            f"Build template should use provided build_dir",
        )

        samconfig = SamConfig(self.working_dir, "samconfig.toml")
        params = samconfig.document.get("default", {}).get("build", {}).get("parameters", {})
        self.assertNotEqual(params, {}, "samconfig.toml was not parsed correctly")
        self.assertIn("parallel", params.keys(), "New key-value pair should be written to config file")
        self.assertTrue(
            params.get("build_dir", None) == "new_dir",
            "New value for existing key build_dir should overwrite old value",
        )


@parameterized_class(
    [  # Ordered by expected priority
        {"extensions": [".toml", ".yaml", ".yml"]},
        {"extensions": [".yaml", ".yml"]},
    ]
)
class TestSamConfigExtensionHierarchy(BuildIntegBase):
    def setUp(self):
        super().setUp()
        new_template_location = Path(self.working_dir, "template.yaml")
        new_template_location.write_text(Path(self.template_path).read_text())
        for extension in self.extensions:
            config_contents = Path(self.test_data_path, configs[extension]).read_text()
            new_path = Path(self.working_dir, f"samconfig{extension}")
            new_path.write_text(config_contents)
            self.assertTrue(new_path.exists(), f"File samconfig{extension} should have been created in cwd")

    def tearDown(self):
        for extension in self.extensions:
            config_path = Path(self.working_dir, f"samconfig{extension}")
            os.remove(config_path)
        super().tearDown()

    def test_samconfig_pulls_correct_file_if_multiple(self):
        self.template_path = str(Path(self.working_dir, "template.yaml"))
        cmdlist = self.get_command_list(debug=True)
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
