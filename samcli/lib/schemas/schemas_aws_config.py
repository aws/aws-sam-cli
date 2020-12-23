""" configure Schemas client based on AWS configuration provided by user """

import click

from boto3.session import Session
from samcli.commands.local.cli_common.user_exceptions import ResourceNotFound


def get_aws_configuration_choice():
    """
    Allow user to select their AWS Connection configuration (profile/region)
    :return: AWS profile and region dictionary
    """
    session = Session()
    profile = session.profile_name
    region = session.region_name

    message = "\nDo you want to use the default AWS profile [%s] and region [%s]?" % (profile, region)
    choice = click.confirm(message, default=True)

    schemas_available_regions_name = session.get_available_regions("schemas")

    if not choice:
        available_profiles = session.available_profiles
        profile = _get_aws_profile_choice(available_profiles)
        region = _get_aws_region_choice(schemas_available_regions_name, region)
    else:
        # session.profile_name will return 'default' if no profile is found,
        # but botocore itself will fail if you pass it in, when one is not configured
        profile = None

    return {"profile": profile, "region": region}


def _get_aws_profile_choice(available_profiles):
    if not available_profiles:
        raise ResourceNotFound("No configured AWS profile found.")

    # Convert list of available profiles (strings) into a list of click.Choice
    # index/string value tuples
    profile_choices = list(map(str, range(1, len(available_profiles) + 1)))
    profile_choice_num = 1

    click.echo("\nWhich AWS profile do you want to use?")

    for profile in available_profiles:
        msg = str(profile_choice_num) + " - " + profile
        click.echo("\t" + msg)
        profile_choice_num = profile_choice_num + 1

    profile_choice = click.prompt("Profile", type=click.Choice(profile_choices), show_choices=False)
    return available_profiles[int(profile_choice) - 1]


def _get_aws_region_choice(available_regions_name, region):
    if not available_regions_name:
        raise ResourceNotFound(
            "No AWS region found for AWS schemas service. This should not be possible, please raise an issue."
        )
    cli_display_regions = dict()

    for available_region_name in available_regions_name:
        region_prefix = available_region_name.rsplit("-", 1)[0]
        if region_prefix not in cli_display_regions:
            cli_display_regions[region_prefix] = available_region_name
        else:
            cli_display_regions[region_prefix] = cli_display_regions.get(region_prefix) + "," + available_region_name

    click.echo("\nWhich region do you want to use for your schema registry?")
    click.echo("# Partial list of AWS regions")
    click.echo("#")

    for cli_display_region in cli_display_regions:
        msg = cli_display_regions[cli_display_region]
        click.echo("# " + msg)

    region_choice = click.prompt("Region " + "[" + region + "]", type=str, show_choices=False)
    return region_choice


def get_schemas_client(profile, region):
    if profile:
        session = Session(profile_name=profile)
    else:
        session = Session()
    return session.client("schemas", region_name=region)
