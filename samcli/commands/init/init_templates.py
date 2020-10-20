"""
Manages the set of application templates.
"""

import itertools
import json
import os
import logging
import platform
import shutil
import subprocess

from pathlib import Path  # must come after Py2.7 deprecation

import click

from samcli.cli.main import global_cfg
from samcli.commands.exceptions import UserException, AppTemplateUpdateException
from samcli.lib.utils import osutils
from samcli.lib.utils.osutils import rmtree_callback
from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING

LOG = logging.getLogger(__name__)


class InvalidInitTemplateError(UserException):
    pass


class InitTemplates:
    def __init__(self, no_interactive=False, auto_clone=True):
        self._repo_url = "https://github.com/awslabs/aws-sam-cli-app-templates.git"
        self._repo_name = "aws-sam-cli-app-templates"
        self._temp_repo_name = "TEMP-aws-sam-cli-app-templates"
        self.repo_path = None
        self.clone_attempted = False
        self._no_interactive = no_interactive
        self._auto_clone = auto_clone

    def prompt_for_location(self, runtime, dependency_manager):
        options = self.init_options(runtime, dependency_manager)
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
            return (template_md["init_location"], "hello-world")
        if template_md.get("directory") is not None:
            return (os.path.join(self.repo_path, template_md["directory"]), template_md["appTemplate"])
        raise InvalidInitTemplateError("Invalid template. This should not be possible, please raise an issue.")

    def location_from_app_template(self, runtime, dependency_manager, app_template):
        options = self.init_options(runtime, dependency_manager)
        try:
            template = next(item for item in options if self._check_app_template(item, app_template))
            if template.get("init_location") is not None:
                return template["init_location"]
            if template.get("directory") is not None:
                return os.path.join(self.repo_path, template["directory"])
            raise InvalidInitTemplateError("Invalid template. This should not be possible, please raise an issue.")
        except StopIteration as ex:
            msg = "Can't find application template " + app_template + " - check valid values in interactive init."
            raise InvalidInitTemplateError(msg) from ex

    def _check_app_template(self, entry, app_template):
        return entry["appTemplate"] == app_template

    def init_options(self, runtime, dependency_manager):
        if self.clone_attempted is False:
            self._clone_repo()
        if self.repo_path is None:
            return self._init_options_from_bundle(runtime, dependency_manager)
        return self._init_options_from_manifest(runtime, dependency_manager)

    def _init_options_from_manifest(self, runtime, dependency_manager):
        manifest_path = os.path.join(self.repo_path, "manifest.json")
        with open(str(manifest_path)) as fp:
            body = fp.read()
            manifest_body = json.loads(body)
            templates = manifest_body.get(runtime)
            if templates is None:
                # Fallback to bundled templates
                return self._init_options_from_bundle(runtime, dependency_manager)
            if dependency_manager is not None:
                templates_by_dep = filter(lambda x: x["dependencyManager"] == dependency_manager, templates)
                return list(templates_by_dep)
            return templates

    def _init_options_from_bundle(self, runtime, dependency_manager):
        for mapping in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values()))):
            if runtime in mapping["runtimes"] or any([r.startswith(runtime) for r in mapping["runtimes"]]):
                if not dependency_manager or dependency_manager == mapping["dependency_manager"]:
                    mapping["appTemplate"] = "hello-world"  # when bundled, use this default template name
                    return [mapping]
        msg = "Lambda Runtime {} and dependency manager {} does not have an available initialization template.".format(
            runtime, dependency_manager
        )
        raise InvalidInitTemplateError(msg)

    def _shared_dir_check(self, shared_dir):
        try:
            shared_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            return True
        except OSError as ex:
            LOG.warning("WARN: Unable to create shared directory.", exc_info=ex)
            return False

    def _clone_repo(self):
        if not self._auto_clone:
            return  # Unit test escape hatch
        # check if we have templates stored already
        shared_dir = global_cfg.config_dir
        if not self._shared_dir_check(shared_dir):
            # Nothing we can do if we can't access the shared config directory, use bundled.
            return
        expected_path = os.path.normpath(os.path.join(shared_dir, self._repo_name))
        if self._template_directory_exists(expected_path):
            self._overwrite_existing_templates(shared_dir, expected_path)
        else:
            # simply create the app templates repo
            self._clone_new_app_templates(shared_dir, expected_path)
        self.clone_attempted = True

    def _overwrite_existing_templates(self, shared_dir, expected_path):
        self.repo_path = expected_path
        # workflow to clone a copy to a new directory and overwrite
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            try:
                expected_temp_path = os.path.normpath(os.path.join(tempdir, self._repo_name))
                LOG.info("\nCloning app templates from %s", self._repo_url)
                subprocess.check_output(
                    [self._git_executable(), "clone", self._repo_url, self._repo_name],
                    cwd=tempdir,
                    stderr=subprocess.STDOUT,
                )
                # Now we need to delete the old repo and move this one.
                self._replace_app_templates(expected_temp_path, expected_path)
                self.repo_path = expected_path
            except OSError as ex:
                LOG.warning("WARN: Could not clone app template repo.", exc_info=ex)
            except subprocess.CalledProcessError as clone_error:
                output = clone_error.output.decode("utf-8")
                if "not found" in output.lower():
                    click.echo("WARN: Could not clone app template repo.")

    def _replace_app_templates(self, temp_path, dest_path):
        try:
            LOG.debug("Removing old templates from %s", str(dest_path))
            shutil.rmtree(dest_path, onerror=rmtree_callback)
            LOG.debug("Copying templates from %s to %s", str(temp_path), str(dest_path))
            shutil.copytree(temp_path, dest_path, ignore=shutil.ignore_patterns("*.git"))
        except (OSError, shutil.Error) as ex:
            # UNSTABLE STATE - it's difficult to see how this scenario could happen except weird permissions, user will need to debug
            raise AppTemplateUpdateException(
                "Unstable state when updating app templates. Check that you have permissions to create/delete files in the AWS SAM shared directory or file an issue at https://github.com/awslabs/aws-sam-cli/issues"
            ) from ex

    def _clone_new_app_templates(self, shared_dir, expected_path):
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            expected_temp_path = os.path.normpath(os.path.join(tempdir, self._repo_name))
            try:
                LOG.info("\nCloning app templates from %s", self._repo_url)
                subprocess.check_output(
                    [self._git_executable(), "clone", self._repo_url], cwd=tempdir, stderr=subprocess.STDOUT
                )
                shutil.copytree(expected_temp_path, expected_path, ignore=shutil.ignore_patterns("*.git"))
                self.repo_path = expected_path
            except OSError as ex:
                LOG.warning("WARN: Can't clone app repo, git executable not found", exc_info=ex)
            except subprocess.CalledProcessError as clone_error:
                output = clone_error.output.decode("utf-8")
                if "not found" in output.lower():
                    click.echo("WARN: Could not clone app template repo.")

    def _template_directory_exists(self, expected_path):
        path = Path(expected_path)
        return path.exists()

    def _git_executable(self):
        execname = "git"
        if platform.system().lower() == "windows":
            options = [execname, "{}.cmd".format(execname), "{}.exe".format(execname), "{}.bat".format(execname)]
        else:
            options = [execname]
        for name in options:
            try:
                subprocess.Popen([name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # No exception. Let's pick this
                return name
            except OSError as ex:
                LOG.debug("Unable to find executable %s", name, exc_info=ex)
        raise OSError("Cannot find git, was looking at executables: {}".format(options))

    def is_dynamic_schemas_template(self, app_template, runtime, dependency_manager):
        """
        Check if provided template is dynamic template e.g: AWS Schemas template.
        Currently dynamic templates require different handling e.g: for schema download and merge schema code in sam-app.
        :param app_template:
        :param runtime:
        :param dependency_manager:
        :return:
        """
        options = self.init_options(runtime, dependency_manager)
        for option in options:
            if option.get("appTemplate") == app_template:
                return option.get("isDynamicTemplate", False)
        return False
