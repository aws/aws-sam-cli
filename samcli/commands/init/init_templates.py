"""
Manages the set of application templates.
"""

import click
import itertools
import json
import os
import shutil
import subprocess

from pathlib import Path  # must come after Py2.7 deprecation

from samcli.cli.main import global_cfg
from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING


class InitTemplates:
    def __init__(self):
        # self._repo_url = "https://github.com/awslabs/aws-sam-cli-app-templates.git"
        # testing only, delete this and uncomment the above line before shipping
        self._repo_url = "git@github.com:awslabs/aws-sam-cli-app-templates.git"
        self._repo_name = "aws-sam-cli-app-templates"
        self.repo_path = None
        self.clone_attempted = False

    def prompt_for_location(self, runtime, dependency_manager):
        options = self.init_options(runtime, dependency_manager)
        choices = map(str, range(1, len(options) + 1))
        choice_num = 1
        for o in options:
            if o.get("displayName") is not None:
                print (choice_num, "-", o.get("displayName"))
            else:
                print (
                    choice_num,
                    "- Default Template for runtime",
                    runtime,
                    "with dependency manager",
                    dependency_manager,
                )
            choice_num = choice_num + 1
        choice = click.prompt("Template Selection", type=click.Choice(choices), show_choices=False)
        template_md = options[int(choice) - 1]  # zero index
        if template_md.get("init_location") is not None:
            return template_md["init_location"]
        elif template_md.get("directory") is not None:
            return os.path.join(self.repo_path, template_md["directory"])
        else:
            raise UserException("Invalid template. This should not be possible, please raise an issue.")

    def init_options(self, runtime, dependency_manager):
        if self.clone_attempted is False:
            self._clone_repo()
        if self.repo_path is None:
            return self._init_options_from_bundle(runtime, dependency_manager)
        else:
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
            else:
                return templates

    def _init_options_from_bundle(self, runtime, dependency_manager):
        for mapping in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values()))):
            if runtime in mapping["runtimes"] or any([r.startswith(runtime) for r in mapping["runtimes"]]):
                if not dependency_manager or dependency_manager == mapping["dependency_manager"]:
                    return [mapping]
        msg = "Lambda Runtime {} and dependency manager {} does not have an available initialization template.".format(
            runtime, dependency_manager
        )
        raise UserException(msg)

    def _clone_repo(self):
        shared_dir = global_cfg.config_dir
        expected_path = os.path.normpath(os.path.join(shared_dir, self._repo_name))
        if self._should_clone_repo(expected_path):
            try:
                subprocess.check_output(["git", "clone", self._repo_url], cwd=shared_dir, stderr=subprocess.STDOUT)
                # check for repo in path?
                self.repo_path = expected_path
            except subprocess.CalledProcessError as clone_error:
                output = clone_error.output.decode("utf-8")
                if "not found" in output.lower():
                    print ("WARN: Could not clone app template repo.")
                # do we ever want to hard fail?
        self._clone_attempted = True

    def _should_clone_repo(self, expected_path):
        path = Path(expected_path)
        if path.exists():
            overwrite = click.confirm("Init templates exist on disk. Do you wish to update?")
            if overwrite:
                # possible alternative: pull down first, THEN delete old version - safer if there is a problem
                shutil.rmtree(expected_path)  # fail hard if there is an issue
                return True
            self.repo_path = expected_path
            return False
        else:
            return True
