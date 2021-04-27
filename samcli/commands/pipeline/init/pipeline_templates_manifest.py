"""
Represents a manifest that lists the available SAM pipeline templates.
Example:
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
from pathlib import Path
from typing import Dict, List

import yaml

from samcli.commands.exceptions import AppPipelineTemplateManifestException
from samcli.yamlhelper import parse_yaml_file


class PipelineTemplateManifest:
    """ The metadata of a Given pipeline template"""

    def __init__(self, manifest: Dict) -> None:
        self.name: str = manifest["name"]
        self.provider: str = manifest["provider"]
        self.location: str = manifest["location"]


class PipelineTemplatesManifest:
    """ The metadata of the available CI/CD providers and the pipeline templates"""

    def __init__(self, manifest_path: Path) -> None:
        try:
            manifest: Dict = parse_yaml_file(file_path=str(manifest_path))
            self.providers: List[str] = manifest["providers"]
            self.templates: List[PipelineTemplateManifest] = list(map(PipelineTemplateManifest, manifest["templates"]))
        except (FileNotFoundError, KeyError, yaml.YAMLError) as ex:
            raise AppPipelineTemplateManifestException(
                "SAM pipeline templates manifest file is not found or ill-formatted. This could happen if the file "
                f"{manifest_path} got deleted or manipulated."
                "If you believe this is not the case, please file an issue at https://github.com/aws/aws-sam-cli/issues"
            ) from ex
