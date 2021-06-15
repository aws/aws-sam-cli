"""
Isolates interactive init prompt flow. Expected to call generator logic at end of flow.
"""
import tempfile
import logging
import click

from botocore.exceptions import ClientError, WaiterError

from samcli.commands.init.interactive_event_bridge_flow import (
    get_schema_template_details,
    get_schemas_api_caller,
    get_schemas_template_parameter,
)
from samcli.commands.exceptions import SchemasApiException
from samcli.lib.schemas.schemas_code_manager import do_download_source_code_binding, do_extract_and_merge_schemas_code
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates
from samcli.lib.utils.osutils import remove
from samcli.lib.utils.packagetype import IMAGE, ZIP

LOG = logging.getLogger(__name__)


def do_interactive(
    location,
    pt_explicit,
    package_type,
    runtime,
    base_image,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
):
    """
    Implementation of the ``cli`` method when --interactive is provided.
    It will ask customers a few questions to init a template.
    """
    if app_template:
        location_opt_choice = "1"
    else:
        click.echo("Which template source would you like to use?")
        click.echo("\t1 - AWS Quick Start Templates\n\t2 - Custom Template Location")
        location_opt_choice = click.prompt("Choice", type=click.Choice(["1", "2"]), show_choices=False)
    if location_opt_choice == "2":
        _generate_from_location(
            location, package_type, runtime, dependency_manager, output_dir, name, app_template, no_input
        )
    else:
        _generate_from_use_case(
            location, package_type, runtime, base_image, dependency_manager, output_dir, name, app_template
        )


def _generate_from_location(
    location, package_type, runtime, dependency_manager, output_dir, name, app_template, no_input
):
    location = click.prompt("\nTemplate location (git, mercurial, http(s), zip, path)", type=str)
    summary_msg = """
-----------------------
Generating application:
-----------------------
Location: {location}
Output Directory: {output_dir}
    """.format(
        location=location, output_dir=output_dir
    )
    click.echo(summary_msg)
    do_generate(location, package_type, runtime, dependency_manager, output_dir, name, no_input, None)


# pylint: disable=too-many-statements
def _generate_from_use_case(
    location, package_type, runtime, base_image, dependency_manager, output_dir, name, app_template
):
    templates = InitTemplates()
    preprocessed_options = templates.get_preprocessed_manifest()

    click.echo("\nWhat is your use-case?")
    use_case = _get_choice_from_options("Use case", preprocessed_options)

    package_types_options = preprocessed_options[use_case]
    click.echo("\nWhat package type would you like to use?")
    package_type = _get_choice_from_options("Package type", package_types_options)

    runtime_options = package_types_options[package_type]
    if package_type == IMAGE:
        click.echo("\nWhich base image would you like to use?")
        base_image = _get_choice_from_options("Image", runtime_options)
        runtime = _get_runtime_from_image(base_image)
        template_runtime = base_image

    else:
        click.echo("\nWhich runtime would you like to use?")
        runtime = _get_choice_from_options("Runtime", runtime_options)
        template_runtime = runtime

    template_options = runtime_options[template_runtime]
    template_choosen = _get_app_template_choice(template_options)
    app_template = template_choosen["appTemplate"]

    dependency_manager = template_choosen["dependencyManager"]
    location = templates.location_from_app_template(package_type, runtime, base_image, dependency_manager, app_template)

    if not name:
        name = click.prompt("\nProject name", type=str, default="sam-app")
    extra_context = {"project_name": name, "runtime": runtime}

    # executing event_bridge logic if call is for Schema dynamic template
    is_dynamic_schemas_template = templates.is_dynamic_schemas_template(
        package_type, app_template, runtime, base_image, dependency_manager
    )
    if is_dynamic_schemas_template:
        schemas_api_caller = get_schemas_api_caller()
        schema_template_details = _get_schema_template_details(schemas_api_caller)
        schemas_template_parameter = get_schemas_template_parameter(schema_template_details)
        extra_context = {**schemas_template_parameter, **extra_context}

    no_input = True
    summary_msg = ""
    if package_type == ZIP:
        summary_msg = f"""
    -----------------------
    Generating application:
    -----------------------
    Name: {name}
    Runtime: {runtime}
    Dependency Manager: {dependency_manager}
    Application Template: {app_template}
    Output Directory: {output_dir}
    
    Next steps can be found in the README file at {output_dir}/{name}/README.md
        """
    elif package_type == IMAGE:
        summary_msg = f"""
    -----------------------
    Generating application:
    -----------------------
    Name: {name}
    Base Image: {base_image}
    Dependency Manager: {dependency_manager}
    Output Directory: {output_dir}

    Next steps can be found in the README file at {output_dir}/{name}/README.md
        """

    click.echo(summary_msg)
    do_generate(location, package_type, runtime, dependency_manager, output_dir, name, no_input, extra_context)
    # executing event_bridge logic if call is for Schema dynamic template
    if is_dynamic_schemas_template:
        _package_schemas_code(runtime, schemas_api_caller, schema_template_details, output_dir, name, location)


def _get_app_template_choice(templates):
    chosen_template = templates[0]
    if len(templates) > 1:
        click.echo("\nSelect your starter template")
        click_template_choices = []
        for idx, template in enumerate(templates):
            click.echo("\t{index} - {name}".format(index=idx + 1, name=template["displayName"]))
            click_template_choices.append(str(idx + 1))
        template_choice = click.prompt("Template", type=click.Choice(click_template_choices), show_choices=False)
        chosen_template = templates[int(template_choice) - 1]
    return chosen_template


def _get_choice_from_options(msg, options):
    options_list = list(options.keys())
    click_choices = []
    for idx, option in enumerate(options_list):
        click.echo("\t{index} - {name}".format(index=idx + 1, name=option))
        click_choices.append(str(idx + 1))
    choice = click.prompt(msg, type=click.Choice(click_choices), show_choices=False)
    choosen = options_list[int(choice) - 1]
    return choosen


def _get_runtime_from_image(image):
    """
    Get corresponding runtime from the base-image parameter
    """
    runtime = image[image.find("/") + 1 : image.find("-")]
    return runtime


def _get_schema_template_details(schemas_api_caller):
    try:
        return get_schema_template_details(schemas_api_caller)
    except ClientError as e:
        raise SchemasApiException(
            "Exception occurs while getting Schemas template parameter. %s" % e.response["Error"]["Message"]
        ) from e


def _package_schemas_code(runtime, schemas_api_caller, schema_template_details, output_dir, name, location):
    try:
        click.echo("Trying to get package schema code")
        download_location = tempfile.NamedTemporaryFile(delete=False)
        do_download_source_code_binding(runtime, schema_template_details, schemas_api_caller, download_location)
        do_extract_and_merge_schemas_code(download_location, output_dir, name, location)
        download_location.close()
    except (ClientError, WaiterError) as e:
        raise SchemasApiException(
            "Exception occurs while packaging Schemas code. %s" % e.response["Error"]["Message"]
        ) from e
    finally:
        remove(download_location.name)
