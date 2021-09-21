"""
Manages the set of application templates.
"""

import itertools
import json
import logging
import os
from pathlib import Path
from typing import Dict

import click

from samcli.cli.main import global_cfg
from samcli.commands.exceptions import UserException, AppTemplateUpdateException
from samcli.lib.utils.git_repo import GitRepo, CloneRepoException, CloneRepoUnstableStateException
from samcli.lib.utils.packagetype import IMAGE
from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING, get_local_lambda_images_location

LOG = logging.getLogger(__name__)
APP_TEMPLATES_REPO_URL = "https://github.com/aws/aws-sam-cli-app-templates"
APP_TEMPLATES_REPO_NAME = "aws-sam-cli-app-templates"


class InvalidInitTemplateError(UserException):
    pass


class InitTemplates:
    def __init__(self, no_interactive=False):
        self._no_interactive = no_interactive
        self._git_repo: GitRepo = GitRepo(url=APP_TEMPLATES_REPO_URL)

    def prompt_for_location(self, package_type, runtime, base_image, dependency_manager):
        """
        Prompt for template location based on other information provided in previous steps.

        Parameters
        ----------
        package_type : str
            the package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
        runtime : str
            the runtime string
        base_image : str
            the base image string
        dependency_manager : str
            the dependency manager string

        Returns
        -------
        location : str
            The location of the template
        app_template : str
            The name of the template
        """
        options = self.init_options(package_type, runtime, base_image, dependency_manager)

        if len(options) == 1:
            template_md = options[0]
        else:
            choices = list(map(str, range(1, len(options) + 1)))
            choice_num = 1
            click.echo("\nAWS quick start application templates:")
            for o in options:
                if o.get("displayName") is not None:
                    msg = "\t" + str(choice_num) + " - " + o.get("displayName")
                    click.echo(msg)
                else:
                    msg = (
                        "\t"
                        + str(choice_num)
                        + " - Default Template for runtime "
                        + runtime
                        + " with dependency manager "
                        + dependency_manager
                    )
                    click.echo(msg)
                choice_num = choice_num + 1
            choice = click.prompt("Template selection", type=click.Choice(choices), show_choices=False)
            template_md = options[int(choice) - 1]  # zero index
        if template_md.get("init_location") is not None:
            return (template_md["init_location"], template_md["appTemplate"])
        if template_md.get("directory") is not None:
            return os.path.join(self._git_repo.local_path, template_md["directory"]), template_md["appTemplate"]
        raise InvalidInitTemplateError("Invalid template. This should not be possible, please raise an issue.")

    def location_from_app_template(self, package_type, runtime, base_image, dependency_manager, app_template):
        options = self.init_options(package_type, runtime, base_image, dependency_manager)
        try:
            template = next(item for item in options if self._check_app_template(item, app_template))
            if template.get("init_location") is not None:
                return template["init_location"]
            if template.get("directory") is not None:
                return os.path.normpath(os.path.join(self._git_repo.local_path, template["directory"]))
            raise InvalidInitTemplateError("Invalid template. This should not be possible, please raise an issue.")
        except StopIteration as ex:
            msg = "Can't find application template " + app_template + " - check valid values in interactive init."
            raise InvalidInitTemplateError(msg) from ex

    @staticmethod
    def _check_app_template(entry: Dict, app_template: str) -> bool:
        # we need to cast it to bool because entry["appTemplate"] can be Any, and Any's __eq__ can return Any
        # detail: https://github.com/python/mypy/issues/5697
        return bool(entry["appTemplate"] == app_template)

    def init_options(self, package_type, runtime, base_image, dependency_manager):
        if not self._git_repo.clone_attempted:
            shared_dir: Path = global_cfg.config_dir
            try:
                self._git_repo.clone(clone_dir=shared_dir, clone_name=APP_TEMPLATES_REPO_NAME, replace_existing=True)
            except CloneRepoUnstableStateException as ex:
                raise AppTemplateUpdateException(str(ex)) from ex
            except (OSError, CloneRepoException):
                # If can't clone, try using an old clone from a previous run if already exist
                expected_previous_clone_local_path: Path = shared_dir.joinpath(APP_TEMPLATES_REPO_NAME)
                if expected_previous_clone_local_path.exists():
                    self._git_repo.local_path = expected_previous_clone_local_path
        if self._git_repo.local_path is None:
            return self._init_options_from_bundle(package_type, runtime, dependency_manager)
        return self._init_options_from_manifest(package_type, runtime, base_image, dependency_manager)

    def _init_options_from_manifest(self, package_type, runtime, base_image, dependency_manager):
        manifest_path = os.path.join(self._git_repo.local_path, "manifest.json")
        with open(str(manifest_path)) as fp:
            body = fp.read()
            manifest_body = json.loads(body)
            templates = None
            if base_image:
                templates = manifest_body.get(base_image)
            elif runtime:
                templates = manifest_body.get(runtime)

            if templates is None:
                # Fallback to bundled templates
                return self._init_options_from_bundle(package_type, runtime, dependency_manager)

            if dependency_manager is not None:
                templates_by_dep = filter(lambda x: x["dependencyManager"] == dependency_manager, list(templates))
                return list(templates_by_dep)
            return list(templates)

    @staticmethod
    def _init_options_from_bundle(package_type, runtime, dependency_manager):
        for mapping in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values()))):
            if runtime in mapping["runtimes"] or any([r.startswith(runtime) for r in mapping["runtimes"]]):
                if not dependency_manager or dependency_manager == mapping["dependency_manager"]:
                    if package_type == IMAGE:
                        mapping["appTemplate"] = "hello-world-lambda-image"
                        mapping["init_location"] = get_local_lambda_images_location(mapping, runtime)
                    else:
                        mapping["appTemplate"] = "hello-world"  # when bundled, use this default template name
                    return [mapping]
        msg = "Lambda Runtime {} and dependency manager {} does not have an available initialization template.".format(
            runtime, dependency_manager
        )
        raise InvalidInitTemplateError(msg)

    def is_dynamic_schemas_template(self, package_type, app_template, runtime, base_image, dependency_manager):
        """
        Check if provided template is dynamic template e.g: AWS Schemas template.
        Currently dynamic templates require different handling e.g: for schema download & merge schema code in sam-app.
        :param package_type:
        :param app_template:
        :param runtime:
        :param base_image:
        :param dependency_manager:
        :return:
        """
        options = self.init_options(package_type, runtime, base_image, dependency_manager)
        for option in options:
            if option.get("appTemplate") == app_template:
                return option.get("isDynamicTemplate", False)
        return False
