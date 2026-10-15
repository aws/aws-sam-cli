"""MicroVM source contexts are packaged, not compiled as Lambda functions."""

from pathlib import Path

from parameterized import parameterized

from samcli.yamlhelper import yaml_parse
from tests.integration.buildcmd.build_integ_base import BuildIntegBase
from tests.testing_utils import run_command


class TestBuildMicrovmImage(BuildIntegBase):
    template = "microvm_image/template.yaml"

    @parameterized.expand([False, True])
    def test_build_relocates_source_context(self, custom_build_dir):
        build_dir = self.custom_build_dir if custom_build_dir else None
        result = run_command(self.get_command_list(build_dir=build_dir), cwd=self.working_dir)
        self.assertEqual(result.process.returncode, 0, result.stderr)
        output = Path(self.custom_build_dir if custom_build_dir else self.default_build_dir) / "template.yaml"
        built = yaml_parse(output.read_text(encoding="utf-8"))
        source = built["Resources"]["Image"]["Properties"]["CodeUri"]
        self.assertEqual((output.parent / source).resolve(), Path(self.template_path).parent / "source")
        self.assertTrue((output.parent / source / "Dockerfile").is_file())
