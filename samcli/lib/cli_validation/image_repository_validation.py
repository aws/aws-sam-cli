"""
Image Repository Option Validation.
This is to be run last after all CLI options have been processed.
"""
import click

from samcli.commands._utils.option_validator import Validator
from samcli.commands._utils.template import get_template_artifacts_format
from samcli.lib.providers.provider import (
    get_resource_full_path_by_id,
    ResourceIdentifier,
)
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.packagetype import IMAGE


def image_repository_validation(func):
    """
    Wrapper Validation function that will run last after the all cli parmaters have been loaded
    to check for conditions surrounding `--image-repository`, `--image-repositories`, and `--resolve-image-repos`. The
    reason they are done last instead of in callback functions, is because the options depend
    on each other, and this breaks cyclic dependencies.

    :param func: Click command function
    :return: Click command function after validation
    """

    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()
        guided = ctx.params.get("guided", False) or ctx.params.get("g", False)
        image_repository = ctx.params.get("image_repository", False)
        image_repositories = ctx.params.get("image_repositories", False) or {}
        resolve_image_repos = ctx.params.get("resolve_image_repos", False)
        parameters_overrides = ctx.params.get("parameters_overrides", {})
        template_file = (
            ctx.params.get("t", False) or ctx.params.get("template_file", False) or ctx.params.get("template", False)
        )

        # Check if `--image-repository`, `--image-repositories`, or `--resolve-image-repos` are required by
        # looking for resources that have an IMAGE based packagetype.

        required = any(
            [
                _template_artifact == IMAGE
                for _template_artifact in get_template_artifacts_format(template_file=template_file)
            ]
        )

        validators = [
            Validator(
                validation_function=lambda: bool(image_repository)
                + bool(image_repositories)
                + bool(resolve_image_repos)
                > 1,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message="Only one of the following can be provided: '--image-repositories', "
                    "'--image-repository', or '--resolve-image-repos'. "
                    "Do you have multiple specified in the command or in a configuration file?",
                ),
            ),
            Validator(
                validation_function=lambda: not guided
                and not (image_repository or image_repositories or resolve_image_repos)
                and required,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message="Missing option '--image-repository', '--image-repositories', or '--resolve-image-repos'",
                ),
            ),
            Validator(
                validation_function=lambda: not guided
                and (
                    image_repositories
                    and not resolve_image_repos
                    and not _is_all_image_funcs_provided(template_file, image_repositories, parameters_overrides)
                ),
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message="Incomplete list of function logical ids specified for '--image-repositories'. "
                    "You can also add --resolve-image-repos to automatically create missing repositories.",
                ),
            ),
        ]
        for validator in validators:
            validator.validate()
        # Call Original function after validation.
        return func(*args, **kwargs)

    return wrapped


def _is_all_image_funcs_provided(template_file, image_repositories, parameters_overrides):
    """
    Validate that the customer provides ECR repository for every available Lambda function with image package type
    """
    image_repositories = image_repositories if image_repositories else {}
    global_parameter_overrides = {}
    stacks, _ = SamLocalStackProvider.get_stacks(
        template_file,
        parameter_overrides=parameters_overrides,
        global_parameter_overrides=global_parameter_overrides,
    )
    # updated_repositories = map_resource_id_key_map_to_full_path(image_repositories, stacks)
    function_provider = SamFunctionProvider(stacks, ignore_code_extraction_warnings=True)

    function_full_paths = {
        function.full_path for function in function_provider.get_all() if function.packagetype == IMAGE
    }

    image_repositories_full_paths = {
        get_resource_full_path_by_id(stacks, ResourceIdentifier(image_repository_id))
        for image_repository_id in image_repositories
    }

    return function_full_paths == image_repositories_full_paths
