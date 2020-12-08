import click

from samcli.commands._utils.option_validator import Validator
from samcli.commands._utils.template import get_template_function_resource_ids, get_template_artifacts_format
from samcli.lib.utils.packagetype import IMAGE


def image_repository_validation(func):
    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()
        guided = ctx.params.get("guided", False) or ctx.params.get("g", False)
        image_repository = ctx.params.get("image_repository", False)
        image_repositories = ctx.params.get("image_repositories", False) or {}
        template_file = (
            ctx.params.get("t", False) or ctx.params.get("template_file", False) or ctx.params.get("template", False)
        )

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
                    message=f"Both '--image-repositories' and '--image-repository' cannot be provided. "
                    f"Do you have both specified in the command or in a configuration file?",
                ),
            ),
            Validator(
                validation_function=lambda: not guided and not (image_repository or image_repositories) and required,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=ctx,
                    message=f"Missing option '--image-repository' or '--image-repositories'",
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
                    message=f"Incomplete list of function logical ids specified for '--image-repositories'",
                ),
            ),
        ]
        for validator in validators:
            validator.validate()
        func(*args, **kwargs)

    return wrapped
