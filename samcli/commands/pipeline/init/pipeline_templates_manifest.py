"""
Represents a manifest that lists the available SAM pipeline templates.
Example:
    providers:
      - displayName:Jenkins
        id: jenkins
      - displayName:Gitlab CI/CD
        id: gitlab
      - displayName:Github Actions
        id: github-actions
    templates:
      - displayName: jenkins-two-environments-pipeline
        provider: Jenkins
        location: templates/cookiecutter-jenkins-two-environments-pipeline
      - displayName: gitlab-two-environments-pipeline
        provider: Gitlab
        location: templates/cookiecutter-gitlab-two-environments-pipeline
      - displayName: Github-Actions-two-environments-pipeline
        provider: Github Actions
        location: templates/cookiecutter-github-actions-two-environments-pipeline
"""
from pathlib import Path
from typing import Dict, List

import yaml  # type: ignore[import]

from samcli.commands.exceptions import AppPipelineTemplateManifestException
from samcli.yamlhelper import parse_yaml_file


class Provider:
    """CI/CD system such as Jenkins, Gitlab and GitHub-Actions"""

    def __init__(self, manifest: Dict) -> None:  # type: ignore[type-arg]
        self.id: str = manifest["id"]
        self.display_name: str = manifest["displayName"]


class PipelineTemplateMetadata:
    """The metadata of a Given pipeline template"""

    def __init__(self, manifest: Dict) -> None:  # type: ignore[type-arg]
        self.display_name: str = manifest["displayName"]
        self.provider: str = manifest["provider"]
        self.location: str = manifest["location"]


class PipelineTemplatesManifest:
    """The metadata of the available CI/CD systems and the pipeline templates"""

    def __init__(self, manifest_path: Path) -> None:
        try:
            manifest: Dict = parse_yaml_file(file_path=str(manifest_path))  # type: ignore[type-arg]
            self.providers: List[Provider] = list(map(Provider, manifest["providers"]))
            self.templates: List[PipelineTemplateMetadata] = list(map(PipelineTemplateMetadata, manifest["templates"]))
        except (FileNotFoundError, KeyError, TypeError, yaml.YAMLError) as ex:
            raise AppPipelineTemplateManifestException(  # type: ignore[no-untyped-call]
                "SAM pipeline templates manifest file is not found or ill-formatted. This could happen if the file "
                f"{manifest_path} got deleted or modified."
                "If you believe this is not the case, please file an issue at https://github.com/aws/aws-sam-cli/issues"
            ) from ex
