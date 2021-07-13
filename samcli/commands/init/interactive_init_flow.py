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
from samcli.lib.iac.interface import ProjectTypes
from samcli.lib.schemas.schemas_code_manager import do_download_source_code_binding, do_extract_and_merge_schemas_code
from samcli.local.common.runtime_template import (
    INIT_RUNTIMES,
    RUNTIME_TO_DEPENDENCY_MANAGERS,
    LAMBDA_IMAGES_RUNTIMES,
    INIT_CDK_LANGUAGES,
    CDK_INIT_RUNTIMES,
)
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates
from samcli.lib.utils.osutils import remove
from samcli.lib.utils.packagetype import IMAGE, ZIP

LOG = logging.getLogger(__name__)


def do_interactive(
    project_type,
    cdk_language,
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
    project_type = _get_project_type(project_type)
    if app_template:
        location_opt_choice = "1"
    else:
        click.echo("Which template source would you like to use?")
        click.echo("\t1 - AWS Quick Start Templates\n\t2 - Custom Template Location")
        location_opt_choice = click.prompt("Choice", type=click.Choice(["1", "2"]), show_choices=False)
    if location_opt_choice == "2":
        _generate_from_location(
            project_type, location, package_type, runtime, dependency_manager, output_dir, name, app_template, no_input
        )
    else:
        if not pt_explicit:
            if project_type == ProjectTypes.CDK:
                cdk_language = _get_cdk_language(cdk_language)
                click.echo("Example CDK project only have ZIP type (artifact is a zip uploaded to S3) now.")
                package_type = ZIP
            else:
                click.echo("What package type would you like to use?")
                click.echo("\t1 - Zip (artifact is a zip uploaded to S3)\t")
                click.echo("\t2 - Image (artifact is an image uploaded to an ECR image repository)")
                package_opt_choice = click.prompt("Package type", type=click.Choice(["1", "2"]), show_choices=False)
                if package_opt_choice == "1":
                    package_type = ZIP
                else:
                    package_type = IMAGE

        _generate_from_app_template(
            project_type,
            cdk_language,
            location,
            package_type,
            runtime,
            base_image,
            dependency_manager,
            output_dir,
            name,
            app_template,
        )


def _generate_from_location(
    project_type, location, package_type, runtime, dependency_manager, output_dir, name, app_template, no_input
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
    do_generate(project_type, location, package_type, runtime, dependency_manager, output_dir, name, no_input, None)


# pylint: disable=too-many-statements
def _generate_from_app_template(
    project_type,
    cdk_language,
    location,
    package_type,
    runtime,
    base_image,
    dependency_manager,
    output_dir,
    name,
    app_template,
):
    extra_context = None
    if package_type == IMAGE:
        base_image, runtime = _get_runtime_from_image(base_image)
    else:
        runtime = _get_runtime(project_type, runtime)
    dependency_manager = _get_dependency_manager(dependency_manager, runtime)
    if not name:
        name = click.prompt("\nProject name", type=str, default="sam-app")
    templates = InitTemplates()
    if app_template is not None:
        location = templates.location_from_app_template(
            project_type, cdk_language, package_type, runtime, base_image, dependency_manager, app_template
        )
        extra_context = {"project_name": name, "runtime": runtime}
    else:
        location, app_template = templates.prompt_for_location(
            project_type, cdk_language, package_type, runtime, base_image, dependency_manager
        )
        extra_context = {"project_name": name, "runtime": runtime}

    # executing event_bridge logic if call is for Schema dynamic template
    is_dynamic_schemas_template = templates.is_dynamic_schemas_template(
        project_type, cdk_language, package_type, app_template, runtime, base_image, dependency_manager
    )
    if is_dynamic_schemas_template:
        schemas_api_caller = get_schemas_api_caller()
        schema_template_details = _get_schema_template_details(schemas_api_caller)
        schemas_template_parameter = get_schemas_template_parameter(schema_template_details)
        extra_context = {**schemas_template_parameter, **extra_context}

    no_input = True
    summary_msg = ""
    cdk_language_msg = f"\n    CDK application language: {cdk_language}\n" if cdk_language else ""
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
    Project Type: {project_type.value} {cdk_language_msg}
    
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
    Project Type: {project_type.value} {cdk_language_msg}

    Next steps can be found in the README file at {output_dir}/{name}/README.md
        """

    click.echo(summary_msg)
    do_generate(
        project_type, location, package_type, runtime, dependency_manager, output_dir, name, no_input, extra_context
    )
    # executing event_bridge logic if call is for Schema dynamic template
    if is_dynamic_schemas_template:
        _package_schemas_code(runtime, schemas_api_caller, schema_template_details, output_dir, name, location)


def _get_project_type(project_type):
    if not project_type:
        click.echo("Which type of project would you like to create?")
        click.echo("\t1 - SAM\n\t2 - CDK")
        project_type_choice = click.prompt("Choice", type=click.Choice(["1", "2"]), show_choices=False)
        if project_type_choice == "1":
            return ProjectTypes.CFN
        return ProjectTypes.CDK
    return project_type


def _get_cdk_language(cdk_language):
    if not cdk_language:
        choices = list(map(str, range(1, len(INIT_CDK_LANGUAGES) + 1)))
        choice_num = 1
        click.echo("\nWhich language would you like to use for the CDK app?")
        for r in INIT_CDK_LANGUAGES:
            msg = "\t" + str(choice_num) + " - " + r
            click.echo(msg)
            choice_num = choice_num + 1
        choice = click.prompt("CDK Language", type=click.Choice(choices), show_choices=False)
        cdk_language = INIT_CDK_LANGUAGES[int(choice) - 1]  # zero index
    return cdk_language


def _get_runtime(project_type, runtime):
    if not runtime:
        init_runtimes = CDK_INIT_RUNTIMES if project_type == ProjectTypes.CDK else INIT_RUNTIMES
        choices = list(map(str, range(1, len(init_runtimes) + 1)))
        choice_num = 1
        click.echo("\nWhich runtime would you like to use?")
        for r in init_runtimes:
            msg = "\t" + str(choice_num) + " - " + r
            click.echo(msg)
            choice_num = choice_num + 1
        choice = click.prompt("Runtime", type=click.Choice(choices), show_choices=False)
        runtime = init_runtimes[int(choice) - 1]  # zero index
    return runtime


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


def _get_dependency_manager(dependency_manager, runtime):
    if not dependency_manager:
        valid_dep_managers = RUNTIME_TO_DEPENDENCY_MANAGERS.get(runtime)
        if valid_dep_managers is None:
            dependency_manager = None
        elif len(valid_dep_managers) == 1:
            dependency_manager = valid_dep_managers[0]
        else:
            choices = list(map(str, range(1, len(valid_dep_managers) + 1)))
            choice_num = 1
            click.echo("\nWhich dependency manager would you like to use?")
            for dm in valid_dep_managers:
                msg = "\t" + str(choice_num) + " - " + dm
                click.echo(msg)
                choice_num = choice_num + 1
            choice = click.prompt("Dependency manager", type=click.Choice(choices), show_choices=False)
            dependency_manager = valid_dep_managers[int(choice) - 1]  # zero index
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
