"""
The plugin's postprocessor prints information about the created and reused AWS resources and the required permissions
"""
import logging
from typing import Dict, List

import click

from samcli.lib.cookiecutter.processor import Processor
from .config import PLUGIN_NAME
from .context import Context as PluginContext
from .resource import Deployer, Resource

LOG = logging.getLogger(__name__)


class Postprocessor(Processor):
    """
    prints information about the created and reused AWS resources and the required permissions

    Attributes
    ----------
    resources_reused:
        A list of the required AWS resources that got provided by the user.
    resources_reused:
        A list of the required AWS resources that the plugin created on behalf of the user.
    """

    def __init__(self) -> None:
        self.resources_reused: List[Dict[str, str]] = []
        self.resources_created: List[Dict[str, str]] = []

    def run(self, context: Dict) -> Dict:
        """
        iterates through the pipeline's AWS resources and categorize them into two categories:
        1. Resources created by the plugin
        2. Resources provided by the user
        It then prints to the user the ARNs of the resources created by the plugin. And for each resource provided
        by the user, it prints instructions about the required IAM policies for this resource to operate as expected,
        so that the user can ensure it already has this permissions.

        Parameters
        ----------
        context: Dict
            A dictionary of the whole context of the cookiecutter template, it contains a key, context[PLUGIN_NAME],
            that contains this plugin's context(object of type PluginContext) where the method extracts its required
            information from.
        """

        context = context.copy()
        plugin_context: PluginContext = context[PLUGIN_NAME]
        deployer: Deployer = plugin_context.deployer
        self._categorize_resource(deployer, plugin_context.deployer_permissions())

        for stage in plugin_context.stages:
            self._categorize_resource(stage.deployer_role, stage.deployer_role_permissions(deployer.arn))
            self._categorize_resource(stage.cfn_deployment_role, stage.cfn_deployment_role_permissions())
            self._categorize_resource(stage.artifacts_bucket, stage.artifacts_bucket_permissions())

        if self.resources_created:
            click.secho("\nWe have created the following resources:", fg="yellow")
            for resource in self.resources_created:
                click.secho(f"\t{resource['arn']}", fg="yellow")

        if self.resources_reused:
            click.secho(
                "\nWe have reused the following resources, please make sure it has the required permissions:",
                fg="yellow",
            )
            for resource in self.resources_reused:
                click.secho(f"\n{resource['arn']}", fg="yellow")
                click.secho(f"Required Permissions: {resource['required_permissions']}", fg="yellow")
            click.echo("\n")

        if not deployer.is_user_provided:
            click.secho(
                "Please set the following variables of the IAM user credentials to your CICD project:", fg="green"
            )
            click.secho(
                f"{plugin_context.deployer_aws_access_key_id_variable_name}: {deployer.access_key_id}", fg="green"
            )
            click.secho(
                f"{plugin_context.deployer_aws_secret_access_key_variable_name}: {deployer.secret_access_key}",
                fg="green",
            )

        return context

    def _categorize_resource(self, resource: Resource, required_permissions: str) -> None:
        """
        add the resource to the corresponding category; reused or created. And store a reference for the resource's
        required permissions in case if it is not created by the plugin

        Parameters
        ----------
        resource: Resource
            The resource to categorized
        required_permissions: str
            the IAM policies required for the resource to operate correctly.
        """
        if resource.is_user_provided:
            self.resources_reused.append({"arn": resource.arn, "required_permissions": required_permissions})
        else:
            self.resources_created.append({"arn": resource.arn})
