"""
Interactive flow that prompts that users for pipeline template (cookiecutter template) and used it to generate
pipeline configuration file
"""
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List

import click

from samcli.cli.main import global_cfg
from samcli.commands.exceptions import PipelineTemplateCloneException
from samcli.lib.cookiecutter.interactive_flow import InteractiveFlow
from samcli.lib.cookiecutter.interactive_flow_creator import InteractiveFlowCreator
from samcli.lib.cookiecutter.template import Template
from samcli.lib.utils.git_repo import GitRepo, CloneRepoException
from samcli.lib.utils.osutils import rmtree_callback
from .pipeline_templates_manifest import PipelineTemplateManifest, PipelineTemplatesManifest

LOG = logging.getLogger(__name__)
shared_path: Path = global_cfg.config_dir
APP_PIPELINE_TEMPLATES_REPO_URL = "https://github.com/aws/aws-sam-cli-pipeline-init-templates.git"
APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME = "aws-sam-cli-app-pipeline-templates"
CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME = "custom-pipeline-template"


def do_interactive() -> None:
    """
    An interactive flow that prompts the user for pipeline template (cookiecutter template) location, downloads it,
    runs its specific questionnaire then generates the pipeline config file based on the template and user's responses
    """
    click.echo("Which pipeline template source would you like to use?")
    click.echo("\t1 - AWS Quick Start Pipeline Templates\n\t2 - Custom Pipeline Template Location")
    location_choice = click.prompt("Choice", type=click.Choice(["1", "2"]), show_choices=False)
    if location_choice == "2":
        _generate_from_custom_location()
    else:
        _generate_from_app_pipeline_templates()


def _generate_from_app_pipeline_templates() -> None:
    """
    Prompts the user to choose a pipeline template from SAM predefined set of pipeline templates hosted in the git
    repository: aws/aws-sam-cli-pipeline-init-templates.git
    downloads locally, then generates the pipeline config file from the selected pipeline template.
    """
    pipeline_templates_local_dir: Path = _clone_app_pipeline_templates()

    pipeline_templates_manifest: PipelineTemplatesManifest = _read_app_pipeline_templates_manifest(
        pipeline_templates_dir=pipeline_templates_local_dir
    )
    # The manifest contains multiple pipeline-templates so select one
    selected_pipeline_template_manifest: PipelineTemplateManifest = _select_pipeline_template(
        pipeline_templates_manifest=pipeline_templates_manifest
    )
    selected_pipeline_template_dir: Path = pipeline_templates_local_dir.joinpath(
        selected_pipeline_template_manifest.location
    )
    _generate_from_pipeline_template(pipeline_template_dir=selected_pipeline_template_dir)


def _generate_from_custom_location() -> None:
    """
    Prompts the user for a custom pipeline template location, downloads locally, then generates the pipeline config file
    """
    pipeline_template_repo_url: str = click.prompt(text="template Git location")
    pipeline_template_local_dir: Path = _clone_custom_pipeline_template(repo_url=pipeline_template_repo_url)
    _generate_from_pipeline_template(pipeline_template_dir=pipeline_template_local_dir)
    # Unlike app pipeline templates, custom pipeline templates are not shared between different SAM applications
    # and should be cleaned up from users' machines after generating the pipeline config files.
    shutil.rmtree(pipeline_template_local_dir, onerror=rmtree_callback)


def _generate_from_pipeline_template(pipeline_template_dir: Path) -> None:
    """
    Generates a pipeline config file from a given pipeline template local location
    """
    pipeline_template: Template = _initialize_pipeline_template(pipeline_template_dir=pipeline_template_dir)
    context: Dict = pipeline_template.run_interactive_flows()
    pipeline_template.generate_project(context)


def _clone_app_pipeline_templates() -> Path:
    """
    clone aws/aws-sam-cli-pipeline-init-templates.git Git repo to the local machine in SAM shared directory.
    Returns:
        the local directory path where the repo is cloned.
    """
    try:
        return _clone_pipeline_templates(
            repo_url=APP_PIPELINE_TEMPLATES_REPO_URL, clone_name=APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME
        )
    except PipelineTemplateCloneException:
        # If can't clone app pipeline templates, try using an old clone from a previous run if already exist
        expected_previous_clone_local_path: Path = shared_path.joinpath(APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME)
        if expected_previous_clone_local_path.exists():
            click.echo("Unable to download updated app pipeline templates, using existing ones")
            return expected_previous_clone_local_path
        raise


def _clone_custom_pipeline_template(repo_url: str) -> Path:
    """
    clone a given Git pipeline template's Git repo to the user machine in SAM shared directory.
    Returns: the local directory path where the repo is cloned to.

    Parameters:
        repo_url: the URL of the Git repo to clone

    Returns:
        the local directory path where the repo is cloned.
    """
    return _clone_pipeline_templates(repo_url=repo_url, clone_name=CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME)


def _clone_pipeline_templates(repo_url: str, clone_name: str) -> Path:
    """
    clone a given pipeline templates' Git repo to the user machine inside the SAM shared directory(default: ~/.aws-sam)
    under the given clone name. For example, if clone_name is "custom-pipeline-template" then the location to clone
    to is "~/.aws-sam/custom-pipeline-template/"

    Parameters:
        repo_url: the URL of the Git repo to clone
        clone_name: The folder name to give to the created clone

    Returns:
        Path to the local clone
    """
    try:
        repo: GitRepo = GitRepo(url=repo_url)
        clone_path: Path = repo.clone(clone_dir=shared_path, clone_name=clone_name, replace_existing=True)
        return clone_path
    except (OSError, CloneRepoException) as ex:
        raise PipelineTemplateCloneException(str(ex)) from ex


def _read_app_pipeline_templates_manifest(pipeline_templates_dir: Path) -> PipelineTemplatesManifest:
    """
    parse and return the manifest yaml file located in the root directory of the SAM pipeline templates folder:

    Parameters:
        pipeline_templates_dir: local directory of SAM pipeline templates

    Raises:
        AppPipelineTemplateManifestException if the manifest is not found, ill-formatted or missing required keys

    Returns:
        The manifest of the pipeline templates
    """
    manifest_path: Path = Path(os.path.normpath(pipeline_templates_dir.joinpath("manifest.yaml")))
    return PipelineTemplatesManifest(manifest_path=manifest_path)


def _select_pipeline_template(pipeline_templates_manifest: PipelineTemplatesManifest) -> PipelineTemplateManifest:
    """
    Prompts the user a list of the available CI/CD providers along with associated app pipeline templates to choose
    one of them

    Parameters:
        pipeline_templates_manifest: A manifest file lists the available providers and the associated pipeline templates

    Returns:
         The manifest (A section in the pipeline_templates_manifest) of the chosen pipeline template;
    """
    provider = _prompt_for_cicd_provider(pipeline_templates_manifest.providers)
    provider_pipeline_templates: List[PipelineTemplateManifest] = list(
        filter(lambda t: t.provider == provider, pipeline_templates_manifest.templates)
    )
    selected_template_manifest: PipelineTemplateManifest = _prompt_for_pipeline_template(provider_pipeline_templates)
    return selected_template_manifest


def _prompt_for_cicd_provider(available_providers: List[str]) -> str:
    """
    Prompts the user a list of the available CI/CD providers to choose from

    Parameters:
        available_providers: List of available CI/CD providers like Jenkins, Gitlab and CircleCI

    Returns:
        The chosen provider
    """
    choices = list(map(str, range(1, len(available_providers) + 1)))
    click.echo("CICD provider")
    for index, provider in enumerate(available_providers):
        click.echo(message=f"\t{index + 1} - {provider}")
    choice = click.prompt(text="Choice", show_choices=False, type=click.Choice(choices))
    return available_providers[int(choice) - 1]


def _prompt_for_pipeline_template(
    available_pipeline_templates_manifests: List[PipelineTemplateManifest],
) -> PipelineTemplateManifest:
    """
    Prompts the user a list of the available pipeline templates to choose from

    Parameters:
        available_pipeline_templates_manifests: List of available pipeline templates manifests

    Returns:
        The chosen pipeline template manifest
    """
    choices = list(map(str, range(1, len(available_pipeline_templates_manifests) + 1)))
    click.echo("Which pipeline template would you like to use?")
    for index, template in enumerate(available_pipeline_templates_manifests):
        click.echo(f"\t{index + 1} - {template.name}")
    choice = click.prompt(text="Choice", show_choices=False, type=click.Choice(choices))
    return available_pipeline_templates_manifests[int(choice) - 1]


def _initialize_pipeline_template(pipeline_template_dir: Path) -> Template:
    """
    Initialize a pipeline template from a given pipeline template (cookiecutter template) location

    Parameters:
        pipeline_template_dir: The local location of the pipeline cookiecutter template

    Returns:
        The initialized pipeline's cookiecutter template
    """
    interactive_flow = _get_pipeline_template_interactive_flow(pipeline_template_dir=pipeline_template_dir)
    return Template(location=str(pipeline_template_dir), interactive_flows=[interactive_flow])


def _get_pipeline_template_interactive_flow(pipeline_template_dir: Path) -> InteractiveFlow:
    """
    A pipeline template defines its own interactive flow (questionnaire) in a JSON file named questions.json located
    in the root directory of the template. This questionnaire defines a set of questions to prompt to the user and
    use the responses as the cookiecutter context

    Parameters:
        pipeline_template_dir: The local location of the pipeline cookiecutter template

    Raises:
        QuestionsNotFoundException: if the pipeline template is missing questions.json file.
        QuestionsFailedParsingException: if questions.json file is ill-formatted or missing required keys.

    Returns:
         The interactive flow
    """
    flow_definition_path: str = os.path.normpath(pipeline_template_dir.joinpath("questions.json"))
    return InteractiveFlowCreator.create_flow(flow_definition_path=flow_definition_path)
