"""
Isolates interactive init prompt flow. Expected to call generator logic at end of flow.
"""
import functools
import re
import tempfile
import logging
from typing import Optional, Tuple
import click

from botocore.exceptions import ClientError, WaiterError

from samcli.commands.init.interactive_event_bridge_flow import (
    get_schema_template_details,
    get_schemas_api_caller,
    get_schemas_template_parameter,
)
from samcli.commands.exceptions import SchemasApiException, InvalidInitOptionException
from samcli.lib.schemas.schemas_code_manager import do_download_source_code_binding, do_extract_and_merge_schemas_code
from samcli.local.common.runtime_template import (
    INIT_RUNTIMES,
    LAMBDA_IMAGES_RUNTIMES_MAP,
    get_provided_runtime_from_custom_runtime,
    is_custom_runtime,
)
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates, InvalidInitTemplateError
from samcli.lib.utils.osutils import remove
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.architecture import X86_64

LOG = logging.getLogger(__name__)


# pylint: disable=too-many-arguments
def do_interactive(
    location,
    pt_explicit,
    package_type,
    runtime,
    architecture,
    base_image,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
    tracing,
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

    generate_application(
        location,
        pt_explicit,
        package_type,
        runtime,
        architecture,
        base_image,
        dependency_manager,
        output_dir,
        name,
        app_template,
        no_input,
        location_opt_choice,
        tracing,
    )


def generate_application(
    location,
    pt_explicit,
    package_type,
    runtime,
    architecture,
    base_image,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
    location_opt_choice,
    tracing,
):  # pylint: disable=too-many-arguments
    """
    The method holds the decision logic for generating an application
    Parameters
    ----------
    location : str
        Location to SAM template
    pt_explicit : bool
        boolean representing if the customer explicitly stated packageType
    package_type : str
        Zip or Image
    runtime : str
        AWS Lambda runtime or Custom runtime
    architecture : str
        The architecture type 'x86_64' and 'arm64' in AWS
    base_image : str
        AWS Lambda base image
    dependency_manager : str
        Runtime's Dependency manager
    output_dir : str
        Project output directory
    name : str
        name of the project
    app_template : str
        AWS Serverless Application template
    no_input : bool
        Whether to prompt for input or to accept default values
        (the default is False, which prompts the user for values it doesn't know for baking)
    location_opt_choice : int
        User input for selecting how to get customer a vended serverless application
    tracing : bool
        boolen value to determine if X-Ray tracing show be activated or not
    """
    if location_opt_choice == "1":
        _generate_from_use_case(
            location,
            pt_explicit,
            package_type,
            runtime,
            base_image,
            dependency_manager,
            output_dir,
            name,
            app_template,
            architecture,
            tracing,
        )

    else:
        _generate_from_location(
            location, package_type, runtime, dependency_manager, output_dir, name, no_input, tracing
        )


# pylint: disable=too-many-statements
def _generate_from_location(location, package_type, runtime, dependency_manager, output_dir, name, no_input, tracing):
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
    do_generate(location, package_type, runtime, dependency_manager, output_dir, name, no_input, None, tracing)


# pylint: disable=too-many-statements
def _generate_from_use_case(
    location: Optional[str],
    pt_explicit: bool,
    package_type: Optional[str],
    runtime: Optional[str],
    base_image: Optional[str],
    dependency_manager: Optional[str],
    output_dir: Optional[str],
    name: Optional[str],
    app_template: Optional[str],
    architecture: Optional[str],
    tracing: Optional[bool],
) -> None:
    templates = InitTemplates()
    runtime_or_base_image = runtime if runtime else base_image
    package_type_filter_value = package_type if pt_explicit else None
    preprocessed_options = templates.get_preprocessed_manifest(
        runtime_or_base_image, app_template, package_type_filter_value, dependency_manager
    )
    question = "Choose an AWS Quick Start application template"
    use_case = _get_choice_from_options(
        None,
        preprocessed_options,
        question,
        "Template",
    )

    default_app_template_properties = _generate_default_hello_world_application(
        use_case, package_type, runtime, base_image, dependency_manager, pt_explicit
    )

    chosen_app_template_properties = _get_app_template_properties(
        preprocessed_options, use_case, base_image, default_app_template_properties
    )
    runtime, base_image, package_type, dependency_manager, template_chosen = chosen_app_template_properties

    if tracing is None:
        tracing = prompt_user_to_enable_tracing()

    app_template = template_chosen["appTemplate"]
    base_image = (
        LAMBDA_IMAGES_RUNTIMES_MAP.get(str(runtime)) if not base_image and package_type == IMAGE else base_image
    )

    if not name:
        name = click.prompt("\nProject name", type=str, default="sam-app")

    location = templates.location_from_app_template(package_type, runtime, base_image, dependency_manager, app_template)

    final_architecture = get_architectures(architecture)
    lambda_supported_runtime = (
        get_provided_runtime_from_custom_runtime(runtime) if is_custom_runtime(runtime) else runtime
    )
    extra_context = {
        "project_name": name,
        "runtime": lambda_supported_runtime,
        "architectures": {"value": final_architecture},
    }

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
        package_type, runtime, base_image, dependency_manager, output_dir, name, app_template, final_architecture
    )

    click.echo(summary_msg)
    next_commands_msg = f"""
    Commands you can use next
    =========================
    [*] Create pipeline: cd {name} && sam pipeline init --bootstrap
    [*] Validate SAM template: sam validate
    [*] Test Function in the Cloud: sam sync --stack-name {{stack-name}} --watch
    """
    click.secho(next_commands_msg, fg="yellow")
    do_generate(
        location,
        package_type,
        lambda_supported_runtime,
        dependency_manager,
        output_dir,
        name,
        no_input,
        extra_context,
        tracing,
    )
    # executing event_bridge logic if call is for Schema dynamic template
    if is_dynamic_schemas_template:
        _package_schemas_code(
            lambda_supported_runtime, schemas_api_caller, schema_template_details, output_dir, name, location
        )


def _generate_default_hello_world_application(
    use_case: str,
    package_type: Optional[str],
    runtime: Optional[str],
    base_image: Optional[str],
    dependency_manager: Optional[str],
    pt_explicit: bool,
) -> Tuple:
    """
    Generate the default Hello World template if Hello World Example is selected

    Parameters
    ----------
    use_case : str
        Type of template example selected
    package_type : Optional[str]
        The package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
    runtime : Optional[str]
        AWS Lambda function runtime
    base_image : Optional[str]
        AWS Lambda function base-image
    dependency_manager : Optional[str]
        dependency manager
    pt_explicit : bool
        True --package-type was passed or Vice versa

    Returns
    -------
    Tuple
        configuration for a default Hello World Example
    """
    is_package_type_image = bool(package_type == IMAGE)
    if use_case == "Hello World Example" and not (runtime or base_image or is_package_type_image or dependency_manager):
        if click.confirm("\nUse the most popular runtime and package type? (Python and zip)"):
            runtime, package_type, dependency_manager, pt_explicit = "python3.9", ZIP, "pip", True
    return (runtime, package_type, dependency_manager, pt_explicit)


def _get_app_template_properties(
    preprocessed_options: dict, use_case: str, base_image: Optional[str], template_properties: Tuple
) -> Tuple:
    """
    This is the heart of the interactive flow, this method fetchs the templates options needed to generate a template

    Parameters
    ----------
    preprocessed_options : dict
        Preprocessed manifest from https://github.com/aws/aws-sam-cli-app-templates
    use_case : Optional[str]
        Type of template example selected
    base_image : str
        AWS Lambda function base-image
    template_properties : Tuple
        Tuple of template properties like runtime, packages type and dependency manager

    Returns
    -------
    Tuple
        Tuple of template configuration and the chosen template

    Raises
    ------
    InvalidInitOptionException
        exception raised when invalid option is provided
    """
    runtime, package_type, dependency_manager, pt_explicit = template_properties
    runtime_options = preprocessed_options[use_case]
    runtime = None if is_custom_runtime(runtime) else runtime
    if not runtime and not base_image:
        question = "Which runtime would you like to use?"
        runtime = _get_choice_from_options(runtime, runtime_options, question, "Runtime")

    if base_image:
        runtime = _get_runtime_from_image(base_image)

    package_types_options = runtime_options.get(runtime)
    if not package_types_options:
        raise InvalidInitOptionException(f"Lambda Runtime {runtime} is not supported for {use_case} examples.")
    if not pt_explicit:
        message = "What package type would you like to use?"
        package_type = _get_choice_from_options(None, package_types_options, message, "Package type")
        if package_type == IMAGE:
            base_image = _get_image_from_runtime(runtime)

    dependency_manager_options = package_types_options.get(package_type)
    if not dependency_manager_options:
        raise InvalidInitOptionException(
            f"{package_type} package type is not supported for {use_case} examples and runtime {runtime} selected."
        )

    dependency_manager = _get_dependency_manager(dependency_manager_options, dependency_manager, runtime)
    template_chosen = _get_app_template_choice(dependency_manager_options, dependency_manager)
    return (runtime, base_image, package_type, dependency_manager, template_chosen)


def prompt_user_to_enable_tracing():
    """
    Prompt user to if X-Ray Tracing should activated for functions in the SAM template and vice versa
    """
    if click.confirm("\nWould you like to enable X-Ray tracing on the function(s) in your application? "):
        doc_link = "https://aws.amazon.com/xray/pricing/"
        click.echo(f"X-Ray will incur an additional cost. View {doc_link} for more details")
        return True
    return False


def _get_choice_from_options(chosen, options, question, msg):

    if chosen:
        return chosen

    click_choices = []

    options_list = options if isinstance(options, list) else list(options.keys())
    options_list = get_sorted_runtimes(options_list) if msg == "Runtime" else options_list

    if not options_list:
        raise InvalidInitOptionException(f"There are no {msg} options available to be selected.")

    if len(options_list) == 1:
        click.echo(
            f"\nBased on your selections, the only {msg} available is {options_list[0]}."
            + f"\nWe will proceed to selecting the {msg} as {options_list[0]}."
        )
        return options_list[0]

    click.echo(f"\n{question}")

    for index, option in enumerate(options_list):
        click.echo(f"\t{index+1} - {option}")
        click_choices.append(str(index + 1))
    choice = click.prompt(msg, type=click.Choice(click_choices), show_choices=False)
    return options_list[int(choice) - 1]


def get_sorted_runtimes(runtime_option_list):
    """
    Return a list of sorted runtimes in ascending order of runtime names and
    descending order of runtime version.

    Parameters
    ----------
    runtime_option_list : list
        list of possible runtime to be selected

    Returns
    -------
    list
        sorted list of possible runtime to be selected
    """
    supported_runtime_list = get_supported_runtime(runtime_option_list)
    return sorted(supported_runtime_list, key=functools.cmp_to_key(compare_runtimes))


def get_supported_runtime(runtime_list):
    """
    Returns a list of only runtimes supported by the current version of SAMCLI.
    This is the list that is presented to the customer to select from.

    Parameters
    ----------
    runtime_list : list
        List of runtime

    Returns
    -------
    list
        List of supported runtime
    """
    supported_runtime_list = []
    error_message = ""
    for runtime in runtime_list:
        if runtime not in INIT_RUNTIMES and not is_custom_runtime(runtime):
            if not error_message:
                error_message = "Additional runtimes may be available in the latest SAM CLI version. \
                    Upgrade your SAM CLI to see the full list."
                LOG.debug(error_message)
            continue
        supported_runtime_list.append(runtime)

    return supported_runtime_list


def compare_runtimes(first_runtime, second_runtime):
    """
    Logic to compare supported runtime for sorting.

    Parameters
    ----------
    first_runtime : str
        runtime to be compared
    second_runtime : str
        runtime to be compared

    Returns
    -------
    int
        comparison result
    """

    first_runtime_name, first_version_number = _split_runtime(first_runtime)
    second_runtime_name, second_version_number = _split_runtime(second_runtime)

    if first_runtime_name == second_runtime_name:
        if first_version_number == second_version_number:
            # If it's the same runtime and version return al2 first
            return -1 if first_runtime.endswith(".al2") else 1
        return second_version_number - first_version_number

    return 1 if first_runtime_name > second_runtime_name else -1


def _split_runtime(runtime):
    """
    Split a runtime into its name and version number.

    Parameters
    ----------
    runtime : str
        Runtime in the format supported by Lambda

    Returns
    -------
    (str, float)
        Tuple of runtime name and runtime version
    """
    return (_get_runtime_name(runtime), _get_version_number(runtime))


def _get_runtime_name(runtime):
    """
    Return the runtime name without the version

    Parameters
    ----------
    runtime : str
        Runtime in the format supported by Lambda.

    Returns
    -------
    str
        Runtime name, which is obtained as everything before the first number
    """
    return re.split(r"\d", runtime)[0]


def _get_version_number(runtime):
    """
    Return the runtime version number

    Parameters
    ----------
    runtime_version : str
        version of a runtime

    Returns
    -------
    float
        Runtime version number
    """

    if is_custom_runtime(runtime):
        return 1.0
    return float(re.search(r"\d+(\.\d+)?", runtime).group())


def _get_app_template_choice(templates_options, dependency_manager):
    templates = _get_templates_with_dependency_manager(templates_options, dependency_manager)
    chosen_template = templates[0]
    if len(templates) > 1:
        click.echo("\nSelect your starter template")
        click_template_choices = []
        for index, template in enumerate(templates):
            click.echo(f"\t{index+1} - {template['displayName']}")
            click_template_choices.append(str(index + 1))
        template_choice = click.prompt("Template", type=click.Choice(click_template_choices), show_choices=False)
        chosen_template = templates[int(template_choice) - 1]
    return chosen_template


def _get_templates_with_dependency_manager(templates_options, dependency_manager):
    return [t for t in templates_options if t.get("dependencyManager") == dependency_manager]


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
    return LAMBDA_IMAGES_RUNTIMES_MAP[runtime]


def _get_dependency_manager(options, dependency_manager, runtime):
    valid_dep_managers = sorted(list(set(template["dependencyManager"] for template in options)))
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
            + "do not have an available initialization template."
        )
        raise InvalidInitTemplateError(msg)
    return dependency_manager


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
        with tempfile.NamedTemporaryFile(delete=False) as download_location:
            do_download_source_code_binding(runtime, schema_template_details, schemas_api_caller, download_location)
            do_extract_and_merge_schemas_code(download_location, output_dir, name, location)
    except (ClientError, WaiterError) as e:
        raise SchemasApiException(
            "Exception occurs while packaging Schemas code. %s" % e.response["Error"]["Message"]
        ) from e
    finally:
        remove(download_location.name)


def get_architectures(architecture):
    """
    Returns list of architecture value based on the init input value
    """
    return [X86_64] if architecture is None else [architecture]


def generate_summary_message(
    package_type, runtime, base_image, dependency_manager, output_dir, name, app_template, architecture
):
    """
    Parameters
    ----------
    package_type : str
        The package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
    runtime : str
        AWS Lambda function runtime
    base_image : str
        base image
    dependency_manager : str
        dependency manager
    output_dir : str
        the directory where project will be generated in
    name : str
        Project Name
    app_template : str
        application template generated
    architecture : list
        Architecture type either x86_64 or arm64 on AWS lambda

    Returns
    -------
    str
        Summary Message of the application template generated
    """

    summary_msg = ""
    if package_type == ZIP:
        summary_msg = f"""
    -----------------------
    Generating application:
    -----------------------
    Name: {name}
    Runtime: {runtime}
    Architectures: {architecture[0]}
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
    Architectures: {architecture[0]}
    Dependency Manager: {dependency_manager}
    Output Directory: {output_dir}

    Next steps can be found in the README file at {output_dir}/{name}/README.md
    """

    return summary_msg
