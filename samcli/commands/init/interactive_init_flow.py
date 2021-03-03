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
from samcli.local.common.runtime_template import LAMBDA_IMAGES_RUNTIMES
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
        _generate_from_use_case(location, runtime, base_image, dependency_manager, output_dir, name, app_template)


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


def _generate_from_use_case(
    location, runtime, base_image, dependency_manager, output_dir, name, app_template
):
    templates = InitTemplates()
    options = templates.use_case_init_options(None, runtime, base_image, dependency_manager)

    click.echo("\nWhat is your use-case?")
    use_cases = list(options.keys())
    click_use_case_choices = []
    for idx, use_case in enumerate(use_cases):
        click.echo("\t{index} - {name}".format(index=idx+1, name=use_case))
        click_use_case_choices.append(str(idx+1))
    use_case_choice = click.prompt("Use case", type=click.Choice(click_use_case_choices), show_choices=False)

    runtimes = list(options[use_cases[int(use_case_choice)-1]].keys())
    if not runtimes:
        click.echo("No templates available for your use case and chosen runtime")
        return

    chosen_runtime = runtimes[0]
    if len(runtimes) > 1:
        click.echo("\nWhat is your runtime?")
        click_runtime_choices = []
        for idx, template_runtime in enumerate(runtimes):
            click.echo("\t{index} - {name}".format(index=idx + 1, name=template_runtime))
            click_runtime_choices.append(str(idx + 1))
        runtime_choice = click.prompt("Runtime", type=click.Choice(click_runtime_choices), show_choices=False)
        chosen_runtime = runtimes[int(runtime_choice)-1]

    # templates is already a list so no need to get the keys and cast
    app_templates = options[use_cases[int(use_case_choice)-1]][chosen_runtime]
    chosen_template = app_templates[0]
    if len(app_templates) > 1:
        click.echo("\nSelect your starter template")
        click_template_choices = []
        for idx, template in enumerate(app_templates):
            click.echo("\t{index} - {name}".format(index=idx+1, name=template["displayName"]))
            click_template_choices.append(str(idx + 1))
        template_choice = click.prompt("Template", type=click.Choice(click_template_choices), show_choices=False)
        chosen_template = app_templates[int(template_choice) - 1]

    if not name:
        name = click.prompt("\nProject name", type=str, default="sam-app")

    package_type = IMAGE if chosen_template["packageType"] == "Image" else ZIP
    extra_context = {"project_name": name, "runtime": runtime}

    # executing event_bridge logic if call is for Schema dynamic template
    is_dynamic_schemas_template = False
    if "isDynamicTemplate" in chosen_template and chosen_template["isDynamicTemplate"] == "True":
        is_dynamic_schemas_template = True

    if is_dynamic_schemas_template:
        schemas_api_caller = get_schemas_api_caller()
        schema_template_details = _get_schema_template_details(schemas_api_caller)
        schemas_template_parameter = get_schemas_template_parameter(schema_template_details)
        extra_context = {**schemas_template_parameter, **extra_context}

    no_input = True
    summary_msg = ""
    runtime = chosen_runtime
    dependency_manager = chosen_template["dependencyManager"]
    app_template = chosen_template["appTemplate"]

    templates.clone_templates_repo()

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


def _get_runtime_from_image(image):
    """
    Get corresponding runtime from the base-image parameter
    """
    if not image:
        choices = list(map(str, range(1, len(LAMBDA_IMAGES_RUNTIMES) + 1)))
        choice_num = 1
        click.echo("\nWhich base image would you like to use?")
        for r in LAMBDA_IMAGES_RUNTIMES:
            msg = "\t" + str(choice_num) + " - " + r
            click.echo(msg)
            choice_num = choice_num + 1
        choice = click.prompt("Base image", type=click.Choice(choices), show_choices=False)
        image = LAMBDA_IMAGES_RUNTIMES[int(choice) - 1]  # zero index

    runtime = image[image.find("/") + 1 : image.find("-")]
    return image, runtime


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
