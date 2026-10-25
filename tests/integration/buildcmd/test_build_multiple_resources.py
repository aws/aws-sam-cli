import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase

from parameterized import parameterized
import yaml

from samcli.yamlhelper import yaml_parse
from tests.testing_utils import get_sam_command


class TestBuildMultipleResources(TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.project = Path(self.temp_dir.name)
        source = self.project / "src"
        source.mkdir()
        (source / "app.py").write_text("def handler(event, context):\n    return event\n")
        (source / "Makefile").write_text('build-%:\n\tcp app.py "$(ARTIFACTS_DIR)/app.py"\n')
        resources = {
            name: {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": "src/",
                    "Handler": "app.handler",
                    "Runtime": "provided.al2023",
                    "Layers": [{"Ref": "Shared"}],
                },
                "Metadata": {"BuildMethod": "makefile"},
            }
            for name in ("First", "Second", "Unselected")
        }
        resources["Shared"] = {
            "Type": "AWS::Serverless::LayerVersion",
            "Properties": {"ContentUri": "src/"},
            "Metadata": {"BuildMethod": "makefile"},
        }
        self.template: dict = {"Transform": "AWS::Serverless-2016-10-31", "Resources": resources}
        (self.project / "template.yaml").write_text(yaml.safe_dump(self.template))

    def _build(self, identifiers: list, options: list) -> subprocess.CompletedProcess:
        return subprocess.run(
            [get_sam_command(), "build", *identifiers, *options, "--output", "json"],
            cwd=self.project,
            env={**os.environ, "SAM_CLI_TELEMETRY": "0"},
            capture_output=True,
            text=True,
            timeout=60,
        )

    @parameterized.expand(
        [
            ("serial", []),
            ("parallel", ["--parallel"]),
            ("cached", ["--cached"]),
            ("cached_parallel", ["--cached", "--parallel"]),
        ]
    )
    def test_builds_one_combined_template(self, _name: str, options: list) -> None:
        for _ in range(2 if "--cached" in options else 1):
            process = self._build(["First", "Second", "Shared", "First"], options)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual({r["resource_id"] for r in result["resources"]}, {"First", "Second", "Shared"})
            self.assertEqual(len(result["resources"]), 3)
            build_dir = self.project / ".aws-sam" / "build"
            built = yaml_parse((build_dir / "template.yaml").read_text())["Resources"]
            for name, property_name in (("First", "CodeUri"), ("Second", "CodeUri"), ("Shared", "ContentUri")):
                artifact = (build_dir / built[name]["Properties"][property_name]).resolve()
                self.assertTrue((artifact / "app.py").is_file(), name)
            self.assertEqual(built["Unselected"]["Properties"]["CodeUri"], "../../src")
            self.assertFalse((build_dir / "Unselected").exists())

    def test_saved_selection_survives_repeated_save_without_arguments(self) -> None:
        for identifiers, options in (
            (["First", "Second"], ["--save-params", "--region", "us-east-1"]),
            ([], []),
            ([], ["--save-params", "--region", "us-east-1"]),
            ([], []),
        ):
            process = self._build(identifiers, options)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertEqual(
                {r["resource_id"] for r in json.loads(process.stdout)["resources"]},
                {"First", "Second", "Shared"},
            )
            self.assertIn('resource_logical_id = ["First", "Second"]', (self.project / "samconfig.toml").read_text())

    def test_rejects_unknown_selection(self) -> None:
        process = self._build(["First", "Missing"], [])
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("Missing", process.stdout + process.stderr)
        self.assertFalse((self.project / ".aws-sam" / "build" / "First" / "app.py").exists())

    def test_builds_root_and_nested_resources_with_the_same_name(self) -> None:
        (self.project / "child.yaml").write_text(yaml.safe_dump(self.template))
        self.template["Resources"]["Child"] = {
            "Type": "AWS::CloudFormation::Stack",
            "Properties": {"TemplateURL": "child.yaml"},
        }
        (self.project / "template.yaml").write_text(yaml.safe_dump(self.template))
        process = self._build(["First", "Child/First", "Shared", "Child/Shared"], ["--parallel"])
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(
            {r["resource_id"] for r in json.loads(process.stdout)["resources"]},
            {"First", "Child/First", "Shared", "Child/Shared"},
        )
        build_dir = self.project / ".aws-sam" / "build"
        root = yaml_parse((build_dir / "template.yaml").read_text())["Resources"]
        child_path = build_dir / root["Child"]["Properties"]["TemplateURL"]
        child = yaml_parse(child_path.read_text())["Resources"]
        for directory, resources in ((build_dir, root), (child_path.parent, child)):
            for name, field in (("First", "CodeUri"), ("Shared", "ContentUri")):
                self.assertTrue((directory / resources[name]["Properties"][field] / "app.py").is_file())
