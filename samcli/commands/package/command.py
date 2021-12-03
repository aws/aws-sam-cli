"""
CLI command for "package" command
"""
import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options, print_cmdline_args
from samcli.commands._utils.cdk_support_decorators import unsupported_command_cdk
from samcli.lib.cli_validation.image_repository_validation import image_repository_validation
from samcli.commands._utils.options import (
    signing_profiles_option,
    s3_bucket_option,
    image_repository_option,
    image_repositories_option,
    s3_prefix_option,
    kms_key_id_option,
    use_json_option,
    force_upload_option,
    resolve_s3_option,
)
from samcli.commands._utils.options import metadata_option, template_click_option, no_progressbar_option
from samcli.lib.utils.resources import resources_generator
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.telemetry.metric import track_command, track_template_warnings
from samcli.lib.utils.version_checker import check_newer_version
from samcli.lib.warnings.sam_cli_warning import CodeDeployWarning, CodeDeployConditionWarning

SHORT_HELP = "Package an AWS SAM application."


def resources_and_properties_help_string():
    """
    Total list of resources and their property locations that are supported for `sam package`
    :return: str
    """
    return "".join(
        f"\nResource : {resource} | Location : {location}\n".format(resource=resource, location=location)
        for resource, location in resources_generator()
    )


HELP_TEXT = (
    """The SAM package command creates and uploads artifacts based on the package type of a given resource.
It uploads local images to ECR for `Image` package types.
It creates zip of your code and dependencies and uploads it to S3 for other package types.
The command returns a copy of your template, replacing references to local artifacts
with the AWS location where the command uploaded the artifacts.

The following resources and their property locations are supported.
"""
    + resources_and_properties_help_string()
)


@click.command("package", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@configuration_option(provider=TomlProvider(section="parameters"))
@template_click_option(include_build=True)
@click.option(
    "--output-template-file",
    required=False,
    type=click.Path(),
    help="The path to the file where the command "
    "writes the output AWS CloudFormation template. If you don't specify a "
    "path, the command writes the template to the standard output.",
)
@s3_bucket_option
@image_repository_option
@image_repositories_option
@s3_prefix_option
@kms_key_id_option
@use_json_option
@force_upload_option
@resolve_s3_option
@metadata_option
@signing_profiles_option
@no_progressbar_option
@common_options
@aws_creds_options
@image_repository_validation
@pass_context
@track_command
@check_newer_version
@track_template_warnings([CodeDeployWarning.__name__, CodeDeployConditionWarning.__name__])
@print_cmdline_args
@unsupported_command_cdk(alternative_command="cdk deploy")
def cli(
    ctx,
    template_file,
    s3_bucket,
    image_repository,
    image_repositories,
    s3_prefix,
    kms_key_id,
    output_template_file,
    use_json,
    force_upload,
    no_progressbar,
    metadata,
    signing_profiles,
    resolve_s3,
    config_file,
    config_env,
):
    """
    `sam package` command entry point
    """
    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        template_file,
        s3_bucket,
        image_repository,
        image_repositories,
        s3_prefix,
        kms_key_id,
        output_template_file,
        use_json,
        force_upload,
        no_progressbar,
        metadata,
        signing_profiles,
        ctx.region,
        ctx.profile,
        resolve_s3,
    )  # pragma: no cover


def do_cli(
    template_file,
    s3_bucket,
    image_repository,
    image_repositories,
    s3_prefix,
    kms_key_id,
    output_template_file,
    use_json,
    force_upload,
    no_progressbar,
    metadata,
    signing_profiles,
    region,
    profile,
    resolve_s3,
):
    """
    Implementation of the ``cli`` method
    """

    from samcli.commands.package.package_context import PackageContext

    if resolve_s3:
        s3_bucket = manage_stack(profile=profile, region=region)
        click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
        click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")
        click.echo("\t\tOr by specifying --s3-bucket explicitly.")

    with PackageContext(
        template_file=template_file,
        s3_bucket=s3_bucket,
        image_repository=image_repository,
        image_repositories=image_repositories,
        s3_prefix=s3_prefix,
        kms_key_id=kms_key_id,
        output_template_file=output_template_file,
        use_json=use_json,
        force_upload=force_upload,
        no_progressbar=no_progressbar,
        metadata=metadata,
        region=region,
        profile=profile,
        signing_profiles=signing_profiles,
    ) as package_context:
        package_context.run()
