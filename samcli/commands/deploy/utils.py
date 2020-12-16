"""
Utilities for sam deploy command
"""

import json
import textwrap

import click


def print_deploy_args(
    stack_name,
    s3_bucket,
    image_repository,
    region,
    capabilities,
    parameter_overrides,
    confirm_changeset,
    signing_profiles,
):
    """
    Print a table of the values that are used during a sam deploy.
    Irrespective of if a image_repository is provided or not, the template is always uploaded to the s3 bucket.

    Example below:

        Deploying with following values
        ===============================
        Stack name                 : sam-app
        Region                     : us-east-1
        Confirm changeset          : False
        Deployment s3 bucket       : aws-sam-cli-managed-default-samclisourcebucket-abcdef
        Capabilities               : ["CAPABILITY_IAM"]
        Parameter overrides        : {'MyParamater': '***', 'Parameter2': 'dd'}
        Signing Profiles           : {'MyFunction': 'ProfileName:ProfileOwner'}

    :param stack_name: Name of the stack used during sam deploy
    :param s3_bucket: Name of s3 bucket used for packaging code artifacts.
    :param image_repository: Name of image repository used for packaging artifacts as container images.
    :param region: Name of region to which the current sam/cloudformation stack will be deployed to.
    :param capabilities: Corresponding IAM capabilities to be used during the stack deploy.
    :param parameter_overrides: Cloudformation parameter overrides to be supplied based on the stack's template
    :param confirm_changeset: Prompt for changeset to be confirmed before going ahead with the deploy.
    :param signing_profiles: Signing profile details which will be used to sign functions/layers
    :return:
    """
    _parameters = parameter_overrides.copy()
    for key, value in _parameters.items():
        if isinstance(value, dict):
            _parameters[key] = value.get("Value", value) if not value.get("Hidden") else "*" * len(value.get("Value"))

    capabilities_string = json.dumps(capabilities)

    _signing_profiles = {}
    if signing_profiles:
        for key, value in signing_profiles.items():
            _signing_profiles[key] = f"{value['profile_name']}:{value['profile_owner']}"

    image_repository_format_text = (
        json.dumps(image_repository, indent=4) if isinstance(image_repository, dict) else image_repository
    )
    parameter_overrides_format_text = json.dumps(_parameters)
    signing_profiles_format_text = json.dumps(signing_profiles)

    click.secho("\n\tDeploying with following values\n\t===============================", fg="yellow")
    click.echo(f"\tStack name                   : {stack_name}")
    click.echo(f"\tRegion                       : {region}")
    click.echo(f"\tConfirm changeset            : {confirm_changeset}")
    if image_repository:
        msg = "Deployment image repository  : "
        # NOTE(sriram-mv): tab length is 8 spaces.
        prefix_length = len(msg) + 8
        click.echo(f"\t{msg}")
        click.echo(f"{textwrap.indent(image_repository_format_text, prefix=' ' * prefix_length)}")
    click.echo(f"\tDeployment s3 bucket         : {s3_bucket}")
    click.echo(f"\tCapabilities                 : {capabilities_string}")
    click.echo(f"\tParameter overrides          : {parameter_overrides_format_text}")
    click.echo(f"\tSigning Profiles             : {signing_profiles_format_text}")

    click.secho("\nInitiating deployment\n=====================", fg="yellow")


def sanitize_parameter_overrides(parameter_overrides):
    """
    Get sanitized parameter override values based on if the workflow went via a guided deploy to set the
    parameter overrides for deployment. If a guided deploy was followed the parameter overrides consists
    of additional information such as if a given parameter's value is hidden or not.
    :param parameter_overrides: dictionary of parameter key values.
    :return:
    """
    return {key: value.get("Value") if isinstance(value, dict) else value for key, value in parameter_overrides.items()}
