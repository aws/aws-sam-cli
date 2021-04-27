from unittest import TestCase
import os
from pathlib import Path
from samcli.commands.pipeline.init.pipeline_templates_manifest import (
    PipelineTemplatesManifest,
    PipelineTemplateManifest,
    AppPipelineTemplateManifestException,
)
from samcli.lib.utils import osutils

INVALID_YAML_MANIFEST = """
providers:
- Jenkins with wrong identation
"""

MISSING_KEYS_MANIFEST = """
NotProviders:
  - Jenkins
Templates:
  - NotName: jenkins-two-stages-pipeline
    provider: Jenkins
    location: templates/cookiecutter-jenkins-two-stages-pipeline
"""

VALID_MANIFEST = """
providers:
  - Jenkins
  - Gitlab
  - Github Actions
templates:
  - name: jenkins-two-stages-pipeline
    provider: Jenkins
    location: templates/cookiecutter-jenkins-two-stages-pipeline
  - name: gitlab-two-stages-pipeline
    provider: Gitlab
    location: templates/cookiecutter-gitlab-two-stages-pipeline
  - name: Github-Actions-two-stages-pipeline
    provider: Github Actions
    location: templates/cookiecutter-github-actions-two-stages-pipeline
"""


class TestCli(TestCase):
    def test_manifest_file_not_found(self):
        non_existing_path = Path(os.path.normpath("/any/non/existing/manifest.yaml"))
        with self.assertRaises(AppPipelineTemplateManifestException):
            PipelineTemplatesManifest(manifest_path=non_existing_path)

    def test_invalid_yaml_manifest_file(self):
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            manifest_path = os.path.normpath(os.path.join(tempdir, "manifest.yaml"))
            with open(manifest_path, "w", encoding="utf-8") as fp:
                fp.write(INVALID_YAML_MANIFEST)
            with self.assertRaises(AppPipelineTemplateManifestException):
                PipelineTemplatesManifest(manifest_path=Path(manifest_path))

    def test_manifest_missing_required_keys(self):
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            manifest_path = os.path.normpath(os.path.join(tempdir, "manifest.yaml"))
            with open(manifest_path, "w", encoding="utf-8") as fp:
                fp.write(MISSING_KEYS_MANIFEST)
            with self.assertRaises(AppPipelineTemplateManifestException):
                PipelineTemplatesManifest(manifest_path=Path(manifest_path))

    def test_manifest_happy_case(self):
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            manifest_path = os.path.normpath(os.path.join(tempdir, "manifest.yaml"))
            with open(manifest_path, "w", encoding="utf-8") as fp:
                fp.write(VALID_MANIFEST)
            manifest = PipelineTemplatesManifest(manifest_path=Path(manifest_path))
        self.assertEquals(manifest.providers, ["Jenkins", "Gitlab", "Github Actions"])
        self.assertEquals(len(manifest.templates), 3)
        gitlab_template: PipelineTemplateManifest = next(t for t in manifest.templates if t.provider == "Gitlab")
        self.assertEquals(gitlab_template.name, "gitlab-two-stages-pipeline")
        self.assertEquals(gitlab_template.provider, "Gitlab")
        self.assertEquals(gitlab_template.location, "templates/cookiecutter-gitlab-two-stages-pipeline")
