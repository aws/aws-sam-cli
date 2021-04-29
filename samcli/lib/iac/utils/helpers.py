"""
Provide Helper methods and decorators to process IAC Plugins
"""
import pathlib

from samcli.cli.context import Context
from samcli.lib.iac.cfn_iac import CfnIacPlugin
from samcli.lib.iac.cdk.plugin import CdkPlugin
from samcli.lib.iac.interface import ProjectTypes, LookupPath, LookupPathType


def inject_iac_plugin(with_build: bool):
    def inner(func):
        def wrapper(*args, **kwargs):
            project_type = kwargs.get("project_type", ProjectTypes.CFN.value)

            iac_plugins = {
                ProjectTypes.CFN.value: CfnIacPlugin,
                ProjectTypes.CDK.value: CdkPlugin,
            }
            ctx = Context.get_current_context()
            iac_plugin = iac_plugins[project_type](ctx)
            lookup_paths = []
            if with_build:
                from samcli.commands.build.command import DEFAULT_BUILD_DIR

                build_dir = kwargs.get("build_dir", DEFAULT_BUILD_DIR)
                lookup_paths.append(LookupPath(build_dir, LookupPathType.BUILD))
            lookup_paths.append(LookupPath(str(pathlib.Path.cwd()), LookupPathType.SOURCE))
            project = iac_plugin.get_project(lookup_paths)

            kwargs["iac"] = iac_plugin
            kwargs["project"] = project

            func(*args, **kwargs)

        return wrapper

    return inner
