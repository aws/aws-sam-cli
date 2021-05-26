from unittest import TestCase
import os
from pathlib import Path
from samcli.commands.pipeline.init.pipeline_templates_manifest import (
    Provider,
    PipelineTemplatesManifest,
    PipelineTemplateMetadata,
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
  - NotName: jenkins-two-environments-pipeline
    provider: Jenkins
    location: templates/cookiecutter-jenkins-two-environments-pipeline
"""

VALID_MANIFEST = """
providers:
  - displayName: Jenkins
    id: jenkins
  - displayName: Gitlab CI/CD
    id: gitlab
  - displayName: Github Actions
    id: github-actions
templates:
  - displayName: jenkins-two-environments-pipeline
    provider: jenkins
    location: templates/cookiecutter-jenkins-two-environments-pipeline
  - displayName: gitlab-two-environments-pipeline
    provider: gitlab
    location: templates/cookiecutter-gitlab-two-environments-pipeline
  - displayName: Github-Actions-two-environments-pipeline
    provider: github-actions
    location: templates/cookiecutter-github-actions-two-environments-pipeline
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
        self.assertEquals(len(manifest.providers), 3)
        gitlab_provider: Provider = next(p for p in manifest.providers if p.id == "gitlab")
        self.assertEquals(gitlab_provider.display_name, "Gitlab CI/CD")
        self.assertEquals(len(manifest.templates), 3)
        gitlab_template: PipelineTemplateMetadata = next(t for t in manifest.templates if t.provider == "gitlab")
        self.assertEquals(gitlab_template.display_name, "gitlab-two-environments-pipeline")
        self.assertEquals(gitlab_template.provider, "gitlab")
        self.assertEquals(gitlab_template.location, "templates/cookiecutter-gitlab-two-environments-pipeline")
