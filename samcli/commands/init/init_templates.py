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
from samcli.commands.exceptions import UserException
from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING

LOG = logging.getLogger(__name__)


class InitTemplates:
    def __init__(self, no_interactive=False, auto_clone=True):
        self._repo_url = "https://github.com/awslabs/aws-sam-cli-app-templates.git"
        self._repo_name = "aws-sam-cli-app-templates"
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
        raise UserException("Invalid template. This should not be possible, please raise an issue.")

    def location_from_app_template(self, runtime, dependency_manager, app_template):
        options = self.init_options(runtime, dependency_manager)
        try:
            template = next(item for item in options if self._check_app_template(item, app_template))
            if template.get("init_location") is not None:
                return template["init_location"]
            if template.get("directory") is not None:
                return os.path.join(self.repo_path, template["directory"])
            raise UserException("Invalid template. This should not be possible, please raise an issue.")
        except StopIteration:
            msg = "Can't find application template " + app_template + " - check valid values in interactive init."
            raise UserException(msg)

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
        raise UserException(msg)

    def _shared_dir_check(self, shared_dir):
        try:
            shared_dir.mkdir(mode=0x700, parents=True, exist_ok=True)
            return True
        except OSError as ex:
            LOG.warning("WARN: Unable to create shared directory.", exc_info=ex)
            return False

    def _clone_repo(self):
        shared_dir = global_cfg.config_dir
        if not self._shared_dir_check(shared_dir):
            return
        expected_path = os.path.normpath(os.path.join(shared_dir, self._repo_name))
        if self._should_clone_repo(expected_path):
            try:
                subprocess.check_output(
                    [self._git_executable(), "clone", self._repo_url], cwd=shared_dir, stderr=subprocess.STDOUT
                )
                self.repo_path = expected_path
            except OSError as ex:
                LOG.warning("WARN: Can't clone app repo, git executable not found", exc_info=ex)
            except subprocess.CalledProcessError as clone_error:
                output = clone_error.output.decode("utf-8")
                if "not found" in output.lower():
                    click.echo("WARN: Could not clone app template repo.")
        self.clone_attempted = True

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

    def _should_clone_repo(self, expected_path):
        path = Path(expected_path)
        if path.exists():
            if not self._no_interactive:
                overwrite = click.confirm(
                    "\nQuick start templates may have been updated. Do you want to re-download the latest", default=True
                )
                if overwrite:
                    shutil.rmtree(expected_path)  # fail hard if there is an issue
                    return True
            self.repo_path = expected_path
            return False

        if self._no_interactive:
            return self._auto_clone
        do_clone = click.confirm(
            "\nAllow SAM CLI to download AWS-provided quick start templates from Github", default=True
        )
        return do_clone
