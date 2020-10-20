"""
CLI command for "package" command
"""
import click

from samcli.cli.cli_config_file import configuration_option, TomlProvider
from samcli.cli.main import pass_context, common_options, aws_creds_options
from samcli.commands._utils.options import metadata_override_option, template_click_option, no_progressbar_option
from samcli.commands._utils.resources import resources_generator
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.telemetry.metrics import track_command, track_template_warnings
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
    """The SAM package command creates a zip of your code and dependencies and uploads it to S3. The command
returns a copy of your template, replacing references to local artifacts with the S3 location where the command
uploaded the artifacts.

The following resources and their property locations are supported.
"""
    + resources_and_properties_help_string()
)


@click.command("package", short_help=SHORT_HELP, help=HELP_TEXT, context_settings=dict(max_content_width=120))
@configuration_option(provider=TomlProvider(section="parameters"))
@template_click_option(include_build=True)
@click.option(
    "--s3-bucket",
    required=False,
    help="The name of the S3 bucket where this command uploads the artifacts that are referenced in your template.",
)
@click.option(
    "--s3-prefix",
    required=False,
    help="A prefix name that the command adds to the artifacts "
    "name when it uploads them to the S3 bucket. The prefix name is a "
    "path name (folder name) for the S3 bucket.",
)
@click.option(
    "--kms-key-id",
    required=False,
    help="The ID of an AWS KMS key that the command uses to encrypt artifacts that are at rest in the S3 bucket.",
)
@click.option(
    "--output-template-file",
    required=False,
    type=click.Path(),
    help="The path to the file where the command "
    "writes the output AWS CloudFormation template. If you don't specify a "
    "path, the command writes the template to the standard output.",
)
@click.option(
    "--use-json",
    required=False,
    is_flag=True,
    help="Indicates whether to use JSON as the format for "
    "the output AWS CloudFormation template. YAML is used by default.",
)
@click.option(
    "--force-upload",
    required=False,
    is_flag=True,
    help="Indicates whether to override existing files "
    "in the S3 bucket. Specify this flag to upload artifacts even if they "
    "match existing artifacts in the S3 bucket.",
)
@click.option(
    "--resolve-s3",
    required=False,
    is_flag=True,
    help="Automatically resolve s3 bucket for non-guided deployments."
    "Do not use --s3-guided parameter with this option.",
)
@metadata_override_option
@no_progressbar_option
@common_options
@aws_creds_options
@pass_context
@track_command
@track_template_warnings([CodeDeployWarning.__name__, CodeDeployConditionWarning.__name__])
def cli(
    ctx,
    template_file,
    s3_bucket,
    s3_prefix,
    kms_key_id,
    output_template_file,
    use_json,
    force_upload,
    no_progressbar,
    metadata,
    resolve_s3,
    config_file,
    config_env,
):

    # All logic must be implemented in the ``do_cli`` method. This helps with easy unit testing

    do_cli(
        template_file,
        s3_bucket,
        s3_prefix,
        kms_key_id,
        output_template_file,
        use_json,
        force_upload,
        no_progressbar,
        metadata,
        ctx.region,
        ctx.profile,
        resolve_s3,
    )  # pragma: no cover


def do_cli(
    template_file,
    s3_bucket,
    s3_prefix,
    kms_key_id,
    output_template_file,
    use_json,
    force_upload,
    no_progressbar,
    metadata,
    region,
    profile,
    resolve_s3,
):
    from samcli.commands.package.package_context import PackageContext
    from samcli.commands.package.exceptions import PackageResolveS3AndS3SetError, PackageResolveS3AndS3NotSetError

    if resolve_s3 and bool(s3_bucket):
        raise PackageResolveS3AndS3SetError()

    if not resolve_s3 and not bool(s3_bucket):
        raise PackageResolveS3AndS3NotSetError()

    if resolve_s3:
        s3_bucket = manage_stack(profile=profile, region=region)
        click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
        click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")
        click.echo("\t\tOr by specifying --s3-bucket explicitly.")

    with PackageContext(
        template_file=template_file,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        kms_key_id=kms_key_id,
        output_template_file=output_template_file,
        use_json=use_json,
        force_upload=force_upload,
        no_progressbar=no_progressbar,
        metadata=metadata,
        region=region,
        profile=profile,
    ) as package_context:
        package_context.run()
