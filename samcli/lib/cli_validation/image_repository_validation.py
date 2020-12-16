"""
Image Repository Option Validation.
This is to be run last after all CLI options have been processed.
"""
import click

from samcli.commands._utils.option_validator import Validator
from samcli.commands._utils.template import get_template_function_resource_ids, get_template_artifacts_format
from samcli.lib.utils.packagetype import IMAGE


def image_repository_validation(func):
    """
    Wrapper Validation function that will run last after the all cli parmaters have been loaded
    to check for conditions surrounding `--image-repository` and `--image-repositories`. The
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
        template_file = (
            ctx.params.get("t", False) or ctx.params.get("template_file", False) or ctx.params.get("template", False)
        )

        # Check if `--image-repository` or `--image-repositories` are required by
        # looking for resources that have an IMAGE based packagetype.

        required = any(
            [
                _template_artifact == IMAGE
                for _template_artifact in get_template_artifacts_format(template_file=template_file)
            ]
        )

        validators = [
            Validator(
                validation_function=lambda: image_repository and image_repositories,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message="Both '--image-repositories' and '--image-repository' cannot be provided. "
                    "Do you have both specified in the command or in a configuration file?",
                ),
            ),
            Validator(
                validation_function=lambda: not guided and not (image_repository or image_repositories) and required,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message="Missing option '--image-repository' or '--image-repositories'",
                ),
            ),
            Validator(
                validation_function=lambda: not guided
                and (
                    set(image_repositories.keys()) != set(get_template_function_resource_ids(template_file, IMAGE))
                    and image_repositories
                ),
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message="Incomplete list of function logical ids specified for '--image-repositories'",
                ),
            ),
        ]
        for validator in validators:
            validator.validate()
        # Call Original function after validation.
        return func(*args, **kwargs)

    return wrapped
