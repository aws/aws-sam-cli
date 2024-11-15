"""
Manages the set of application templates.
"""

import itertools
import json
import logging
import os
from enum import Enum
from pathlib import Path
from subprocess import STDOUT, CalledProcessError, check_output
from typing import Dict, Optional

import requests

from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import AppTemplateUpdateException, UserException
from samcli.commands.init.init_flow_helpers import (
    _get_runtime_from_image,
)
from samcli.lib.utils import configuration
from samcli.lib.utils.git_repo import (
    CloneRepoException,
    CloneRepoUnstableStateException,
    GitRepo,
    ManifestNotFoundException,
)
from samcli.lib.utils.packagetype import IMAGE
from samcli.local.common.runtime_template import (
    RUNTIME_DEP_TEMPLATE_MAPPING,
    get_local_lambda_images_location,
    get_local_manifest_path,
    get_provided_runtime_from_custom_runtime,
    is_custom_runtime,
)

LOG = logging.getLogger(__name__)
APP_TEMPLATES_REPO_COMMIT = configuration.get_app_template_repo_commit()
MANIFEST_URL = (
    f"https://raw.githubusercontent.com/aws/aws-sam-cli-app-templates/{APP_TEMPLATES_REPO_COMMIT}/manifest-v2.json"
)
APP_TEMPLATES_REPO_URL = "https://github.com/aws/aws-sam-cli-app-templates"
APP_TEMPLATES_REPO_NAME = "aws-sam-cli-app-templates"
APP_TEMPLATES_REPO_NAME_WINDOWS = "tmpl"


class Status(Enum):
    NOT_FOUND = 404


class InvalidInitTemplateError(UserException):
    pass


class InitTemplates:
    def __init__(self):
        self._git_repo: GitRepo = GitRepo(url=APP_TEMPLATES_REPO_URL)
        self.manifest_file_name = "manifest-v2.json"

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
        self.clone_templates_repo()
        if self._git_repo.local_path is None:
            return self._init_options_from_bundle(package_type, runtime, dependency_manager)
        return self._init_options_from_manifest(package_type, runtime, base_image, dependency_manager)

    def clone_templates_repo(self):
        if not self._git_repo.clone_attempted:
            from platform import system

            shared_dir: Path = GlobalConfig().config_dir

            os_name = system().lower()
            cloned_folder_name = APP_TEMPLATES_REPO_NAME_WINDOWS if os_name == "windows" else APP_TEMPLATES_REPO_NAME

            if not self._check_upsert_templates(shared_dir, cloned_folder_name):
                return

            try:
                self._git_repo.clone(
                    clone_dir=shared_dir,
                    clone_name=cloned_folder_name,
                    replace_existing=True,
                    commit=APP_TEMPLATES_REPO_COMMIT,
                )
            except CloneRepoUnstableStateException as ex:
                raise AppTemplateUpdateException(str(ex)) from ex
            except (OSError, CloneRepoException):
                LOG.debug("Clone error, attempting to use an old clone from a previous run")
                expected_previous_clone_local_path: Path = shared_dir.joinpath(cloned_folder_name)
                if expected_previous_clone_local_path.exists():
                    self._git_repo.local_path = expected_previous_clone_local_path

    def _check_upsert_templates(self, shared_dir: Path, cloned_folder_name: str) -> bool:
        """
        Check if the app templates repository should be cloned, or if cloning should be skipped.

        Parameters
        ----------
        shared_dir: Path
            Folder containing the aws-sam-cli shared data

        cloned_folder_name: str
            Name of the directory into which the app templates will be copied

        Returns
        -------
        bool
            True if the cache should be updated, False otherwise

        """
        cache_dir = Path(shared_dir, cloned_folder_name)
        git_executable = self._git_repo.git_executable()
        command = [git_executable, "rev-parse", "--verify", "HEAD"]
        try:
            existing_hash = check_output(command, cwd=cache_dir, stderr=STDOUT).decode("utf-8").strip()
        except CalledProcessError as ex:
            LOG.debug(f"Unable to check existing cache hash\n{ex.output.decode('utf-8')}")
            return True
        except (FileNotFoundError, NotADirectoryError):
            LOG.debug("Cache directory does not yet exist, creating one.")
            return True
        self._git_repo.local_path = cache_dir
        return not existing_hash == APP_TEMPLATES_REPO_COMMIT

    def _init_options_from_manifest(self, package_type, runtime, base_image, dependency_manager):
        manifest_path = self.get_manifest_path()
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

    def get_app_template_location(self, template_directory):
        return os.path.normpath(os.path.join(self._git_repo.local_path, template_directory))

    def get_manifest_path(self):
        if self._git_repo.local_path and Path(self._git_repo.local_path, self.manifest_file_name).exists():
            return Path(self._git_repo.local_path, self.manifest_file_name)
        return get_local_manifest_path()

    def get_preprocessed_manifest(
        self,
        filter_value: Optional[str] = None,
        app_template: Optional[str] = None,
        package_type: Optional[str] = None,
        dependency_manager: Optional[str] = None,
    ) -> dict:
        """
        This method get the manifest cloned from the git repo and preprocessed it.
        Below is the link to manifest:
        https://github.com/aws/aws-sam-cli-app-templates/blob/master/manifest-v2.json
        The structure of the manifest is shown below:
        {
            "dotnet6": [
                {
                    "directory": "dotnet6/hello",
                    "displayName": "Hello World Example",
                    "dependencyManager": "cli-package",
                    "appTemplate": "hello-world",
                    "packageType": "Zip",
                    "useCaseName": "Hello World Example"
                },
            ]
        }
        Parameters
        ----------
        filter_value : string, optional
            This could be a runtime or a base-image, by default None
        app_template : string, optional
            Application template generated
        package_type : string, optional
            The package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
        dependency_manager : string, optional
            dependency manager
        Returns
        -------
        [dict]
            This is preprocessed manifest with the use_case as key
        """
        manifest_body = self._get_manifest()

        # This would ensure the Use-Case Hello World Example appears
        # at the top of list template example displayed to the Customer.
        preprocessed_manifest = {"Hello World Example": {}}  # type: dict
        for template_runtime in manifest_body:
            if not filter_value_matches_template_runtime(filter_value, template_runtime):
                LOG.debug("Template runtime %s does not match filter value %s", template_runtime, filter_value)
                continue
            template_list = manifest_body[template_runtime]
            for template in template_list:
                template_package_type = get_template_value("packageType", template)
                use_case_name = get_template_value("useCaseName", template)
                if not (template_package_type or use_case_name) or template_does_not_meet_filter_criteria(
                    app_template, package_type, dependency_manager, template
                ):
                    continue
                runtime = get_runtime(template_package_type, template_runtime)
                if runtime is None:
                    LOG.debug("Unable to infer runtime for template %s, %s", template_package_type, template_runtime)
                    continue
                use_case = preprocessed_manifest.get(use_case_name, {})
                use_case[runtime] = use_case.get(runtime, {})
                use_case[runtime][template_package_type] = use_case[runtime].get(template_package_type, [])
                use_case[runtime][template_package_type].append(template)

                preprocessed_manifest[use_case_name] = use_case

        if not bool(preprocessed_manifest["Hello World Example"]):
            del preprocessed_manifest["Hello World Example"]

        return preprocessed_manifest

    def _get_manifest(self):
        """
        In an attempt to reduce initial wait time to achieve an interactive
        flow <= 10sec, This method first attempts to spools just the manifest file and
        if the manifest can't be spooled, it attempts to clone the cli template git repo or
        use local cli template
        """
        try:
            response = requests.get(MANIFEST_URL, timeout=10)
            if not response.ok:
                # if the commit is not exist then MANIFEST_URL will be invalid,
                # fall back to use manifest in latest commit
                if response.status_code == Status.NOT_FOUND.value:
                    LOG.warning(
                        "Request to MANIFEST_URL: %s failed, the commit hash in this url maybe invalid, "
                        "Using manifest.json in the latest commit instead.",
                        MANIFEST_URL,
                    )
                else:
                    LOG.debug(
                        "Request to MANIFEST_URL: %s failed, with %s status code", MANIFEST_URL, response.status_code
                    )
                raise ManifestNotFoundException()
            body = response.text
        except (requests.Timeout, requests.ConnectionError, ManifestNotFoundException):
            LOG.debug("Request to get Manifest failed, attempting to clone the repository")
            self.clone_templates_repo()
            manifest_path = self.get_manifest_path()
            with open(str(manifest_path)) as fp:
                body = fp.read()
        manifest_body = json.loads(body)
        return manifest_body


def get_template_value(value: str, template: dict) -> Optional[str]:
    if value not in template:
        LOG.debug(
            f"Template is missing the value for {value} in manifest file. Please raise a github issue."
            + f" Template details: {template}"
        )
    return template.get(value)


def get_runtime(package_type: Optional[str], template_runtime: str) -> Optional[str]:
    if package_type == IMAGE:
        return _get_runtime_from_image(template_runtime)
    return template_runtime


def template_does_not_meet_filter_criteria(
    app_template: Optional[str], package_type: Optional[str], dependency_manager: Optional[str], template: dict
) -> bool:
    """
    Parameters
    ----------
    app_template : Optional[str]
        Application template generated
    package_type : Optional[str]
        The package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
    dependency_manager : Optional[str]
        Dependency manager
    template : dict
        key-value pair app template configuration

    Returns
    -------
    bool
        True if template does not meet filter criteria else False
    """
    return bool(
        (app_template and app_template != template.get("appTemplate"))
        or (package_type and package_type != template.get("packageType"))
        or (dependency_manager and dependency_manager != template.get("dependencyManager"))
    )


def filter_value_matches_template_runtime(filter_value, template_runtime):
    """
    Validate if the filter value matches template runtimes from the manifest file

    Parameters
    ----------
    filter_value : str
        Lambda runtime used to filter through data generated from the manifest
    template_runtime : str
        Runtime of the template in view

    Returns
    -------
    bool
        True if there is a match else False
    """
    if not filter_value:
        return True
    if is_custom_runtime(filter_value) and filter_value != get_provided_runtime_from_custom_runtime(template_runtime):
        return False
    if not is_custom_runtime(filter_value) and filter_value != template_runtime:
        return False
    return True
