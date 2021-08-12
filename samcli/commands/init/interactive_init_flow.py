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
from samcli.commands.exceptions import SchemasApiException, InvalidInitOptionException
from samcli.lib.schemas.schemas_code_manager import do_download_source_code_binding, do_extract_and_merge_schemas_code
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates, InvalidInitTemplateError
from samcli.lib.utils.osutils import remove
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.local.common.runtime_template import (
    RUNTIME_DEP_TEMPLATE_MAPPING,
    RUNTIME_TO_DEPENDENCY_MANAGERS,
    LAMBDA_IMAGES_RUNTIMES_MAP,
    INIT_RUNTIMES,
)

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
        location_opt_choice = "2"
    else:
        click.echo("Which template source would you like to use?")
        click.echo("\t1 - Hello World application\n\t2 - AWS Quick Start Templates\n\t3 - Custom Template Location")
        location_opt_choice = click.prompt("Choice", type=click.Choice(["1", "2", "3"]), show_choices=False)

        get_start_options(
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
            location_opt_choice,
        )


def get_start_options(
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
    location_opt_choice,
):
    if location_opt_choice == "1":
        _generate_simple_application(
            location, pt_explicit, runtime, base_image, dependency_manager, output_dir, name, app_template, package_type
        )

    elif location_opt_choice == "2":
        _generate_from_use_case(
            location, pt_explicit, package_type, runtime, base_image, dependency_manager, output_dir, name, app_template
        )

    else:
        _generate_from_location(
            location, package_type, runtime, dependency_manager, output_dir, name, app_template, no_input
        )


# pylint: disable=too-many-statements
def _generate_simple_application(
    location, pt_explicit, runtime, base_image, dependency_manager, output_dir, name, app_template, package_type=ZIP
):
    if pt_explicit and package_type == IMAGE:
        raise InvalidInitOptionException("Hello World Application only supports ZIP package type")

    templates = InitTemplates()
    if not runtime:
        question = (
            "Which runtime would you like to use? "
            + "We will default to the latest supported version of your selected runtime."
        )
        runtime_list = sorted(RUNTIME_DEP_TEMPLATE_MAPPING.keys())
        runtime_choosen = _get_choice_from_options(runtime, runtime_list, question, "Runtime")
        runtime_templates = RUNTIME_DEP_TEMPLATE_MAPPING[runtime_choosen]
        runtime = runtime_templates[0]["runtimes"][0]

    dependency_manager = _get_dependency_manager(None, dependency_manager, runtime)
    bundle_template = templates.get_bundle_option(package_type, runtime, dependency_manager)
    template = bundle_template[0]
    app_template = template["appTemplate"]
    location = template["init_location"]

    if not name:
        name = click.prompt("\nProject name", type=str, default="sam-app")
    extra_context = {"project_name": name, "runtime": runtime}

    no_input = True
    summary_msg = generate_summary_message(
        package_type, runtime, base_image, dependency_manager, output_dir, name, app_template
    )
    click.echo(summary_msg)
    do_generate(location, package_type, runtime, dependency_manager, output_dir, name, no_input, extra_context)


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
    location, pt_explicit, package_type, runtime, base_image, dependency_manager, output_dir, name, app_template
):

    templates = InitTemplates()
    filter_value = runtime if runtime else base_image
    preprocessed_options = templates.get_preprocessed_manifest(filter_value)
    question = "What template would you like to start with?"
    use_case = _get_choice_from_options(
        None,
        preprocessed_options,
        question,
        "Template",
    )
    runtime_options = preprocessed_options[use_case]
    if not runtime and not base_image:
        question = "Which runtime would you like to use?"
        runtime = _get_choice_from_options(runtime, runtime_options, question, "Runtime")

    if base_image:
        runtime = _get_runtime_from_image(base_image)

    try:
        package_types_options = runtime_options[runtime]
        if not pt_explicit:
            message = "What package type would you like to use?"
            package_type = _get_choice_from_options(None, package_types_options, message, "Package type")
            if package_type == IMAGE:
                base_image = _get_image_from_runtime(runtime)
    except Exception as ex:
        raise InvalidInitOptionException(f"Lambda Runtime {runtime} is not supported for {use_case} examples.") from ex

    try:
        dependency_manager_options = package_types_options[package_type]
        dependency_manager = _get_dependency_manager(dependency_manager_options, dependency_manager, runtime)

    except Exception as ex:
        raise InvalidInitOptionException(
            f"{package_type} package type is not supported for {use_case} examples and runtime {runtime} selected."
        ) from ex

    template_choosen = _get_app_template_choice(dependency_manager_options, dependency_manager)
    app_template = template_choosen["appTemplate"]
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
    summary_msg = generate_summary_message(
        package_type, runtime, base_image, dependency_manager, output_dir, name, app_template
    )

    click.echo(summary_msg)
    do_generate(location, package_type, runtime, dependency_manager, output_dir, name, no_input, extra_context)
    # executing event_bridge logic if call is for Schema dynamic template
    if is_dynamic_schemas_template:
        _package_schemas_code(runtime, schemas_api_caller, schema_template_details, output_dir, name, location)


def _get_app_template_choice(templates_options, dependency_manager):
    templates = _get_templates_with_dependency_manager(templates_options, dependency_manager)
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


def _get_templates_with_dependency_manager(templates_options, dependency_manager):
    templates = []
    for template in templates_options:
        if template["dependencyManager"] == dependency_manager:
            templates.append(template)
    return templates


def _get_choice_from_options(choosen, options, question, msg):

    if not choosen:
        click_choices = []

        options_list = options if isinstance(options, list) else list(options.keys())

        if len(options_list) == 1:
            choosen = options_list[0]
            click.echo(
                f"\nBased on your selections, the only {msg} available is {choosen}."
                + f"\nWe will proceed to selecting the {msg} as {choosen}."
            )
        else:
            click.echo(f"\n{question}")
            options_list = (
                get_sorted_runtimes(options_list)
                if msg == "Runtime" and not isinstance(options, list)
                else options_list
            )
            for idx, option in enumerate(options_list):
                click.echo("\t{index} - {name}".format(index=idx + 1, name=option))
                click_choices.append(str(idx + 1))
            choice = click.prompt(msg, type=click.Choice(click_choices), show_choices=False)
            choosen = options_list[int(choice) - 1]
    return choosen


def get_sorted_runtimes(options_list):
    """
    sort lst of runtime name in an ascending order and version in a descending order

    Parameters
    ----------
    options_list : [list]
        list of runtimes

    Returns
    -------
    [list]
        list of sorted runtimes
    """
    runtimes = []
    for runtime in options_list:
        position = INIT_RUNTIMES.index(runtime)
        runtimes.append(position)
    sorted_runtimes = sorted(runtimes)
    for index, position in enumerate(sorted_runtimes):
        sorted_runtimes[index] = INIT_RUNTIMES[position]
    return sorted_runtimes


def _get_runtime_from_image(image):
    """
    Get corresponding runtime from the base-image parameter
    """
    runtime = image[image.find("/") + 1 : image.find("-")]
    return runtime


def _get_image_from_runtime(runtime):
    """
    Get corresponding base-image from the runtime parameter
    """
    image = LAMBDA_IMAGES_RUNTIMES_MAP[runtime]
    return image


def _get_schema_template_details(schemas_api_caller):
    try:
        return get_schema_template_details(schemas_api_caller)
    except ClientError as e:
        raise SchemasApiException(
            "Exception occurs while getting Schemas template parameter. %s" % e.response["Error"]["Message"]
        ) from e


def _get_dependency_manager(options, dependency_manager, runtime):

    valid_dep_managers = (
        RUNTIME_TO_DEPENDENCY_MANAGERS.get(runtime)
        if not options
        else list(set(template["dependencyManager"] for template in options))
    )
    if not dependency_manager:
        if len(valid_dep_managers) == 1:
            dependency_manager = valid_dep_managers[0]
            click.echo(
                f"\nBased on your selections, the only dependency manager available is {dependency_manager}."
                + f"\nWe will proceed copying the template using {dependency_manager}."
            )
        else:
            question = "Which dependency manager would you like to use?"
            dependency_manager = _get_choice_from_options(
                dependency_manager, valid_dep_managers, question, "Dependency manager"
            )
    elif dependency_manager and dependency_manager not in valid_dep_managers:
        msg = (
            f"Lambda Runtime {runtime} and dependency manager {dependency_manager} "
            + "does not have an available initialization template."
        )
        raise InvalidInitTemplateError(msg)
    return dependency_manager


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


def generate_summary_message(package_type, runtime, base_image, dependency_manager, output_dir, name, app_template):
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

    return summary_msg
