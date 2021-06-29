"""
Provide Helper methods and decorators to process IAC Plugins
"""
import logging
import pathlib

import click

from samcli.lib.iac.cfn_iac import CfnIacPlugin
from samcli.lib.iac.cdk.plugin import CdkPlugin
from samcli.lib.iac.interface import ProjectTypes, LookupPath, LookupPathType


LOG = logging.getLogger(__name__)


def get_iac_plugin(project_type, command_params, with_build):
    LOG.debug("IAC Plugin getting project...")
    iac_plugins = {
        ProjectTypes.CFN.value: CfnIacPlugin,
        ProjectTypes.CDK.value: CdkPlugin,
    }
    if project_type is None or project_type not in iac_plugins:
        raise click.BadOptionUsage(
            option_name="--project-type",
            message=f"{project_type} is invalid project type option value, the value should be one"
            f"of the following {[ptype.value for ptype in ProjectTypes]} ",
        )
    iac_plugin = iac_plugins[project_type](command_params)
    lookup_paths = []

    if with_build:
        from samcli.commands.build.command import DEFAULT_BUILD_DIR

        # is this correct? --build-dir is only used for "build" (for writing)
        # but with_true is True for "local" commands only
        build_dir = command_params.get("build_dir", DEFAULT_BUILD_DIR)
        lookup_paths.append(LookupPath(build_dir, LookupPathType.BUILD))
    lookup_paths.append(LookupPath(str(pathlib.Path.cwd()), LookupPathType.SOURCE))
    project = iac_plugin.get_project(lookup_paths)

    return iac_plugin, project


def inject_iac_plugin(with_build: bool):
    def inner(func):
        def wrapper(*args, **kwargs):
            project_type = kwargs.get("project_type", ProjectTypes.CFN.value)

            iac_plugin, project = get_iac_plugin(project_type, kwargs, with_build)

            kwargs["iac"] = iac_plugin
            kwargs["project"] = project

            return func(*args, **kwargs)

        return wrapper

    return inner
