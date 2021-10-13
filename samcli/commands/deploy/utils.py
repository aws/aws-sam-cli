"""
Utilities for sam deploy command
"""

import json
import textwrap
import copy

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
    use_changeset,
    disable_rollback,
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
        Disable rollback           : False
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
    :param use_changeset: Flag to use or skip the usage of changesets
    :param disable_rollback: Preserve the state of previously provisioned resources when an operation fails.
    """
    _parameters = parameter_overrides.copy()

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
    if use_changeset:
        click.echo(f"\tConfirm changeset            : {confirm_changeset}")
    click.echo(f"\tDisable rollback             : {disable_rollback}")
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


def hide_noecho_parameter_overrides(template_parameters, parameter_overrides):
    hidden_params = copy.deepcopy(parameter_overrides)
    params = template_parameters.get("Parameters", None)
    for key, value in hidden_params.items():
        if isinstance(params, dict) and key in params and isinstance(params[key], dict):
            is_hidden = params[key].get("NoEcho", False)
            hidden_params[key] = value if not is_hidden else "*" * 5
    return hidden_params
