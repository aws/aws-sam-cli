"""
Option validation for IAC Plugin
Use as decorator and place the decorator after:
1. all CLI options have been processed.
2. iac plugin has been injected
"""
import functools
import logging
import click

from samcli.lib.iac.interface import ProjectTypes


LOG = logging.getLogger(__name__)


def iac_options_validation(require_stack=False):
    """
    Wrapper validation function that will run after cli parameters have been loaded
    and iac plugin has been injected. Validations vary based on project type.

    :param require_stack: a boolean flag to set whether --stack-name is required or not
    :return: Click command function after validation
    """

    def inner(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            ctx = click.get_current_context()
            selected_project_type = ctx.params.get("project_type")

            project_type_options_map = {
                ProjectTypes.CFN.value: {},
                ProjectTypes.CDK.value: {
                    "cdk_app": "--cdk-app",
                    "cdk_context": "--cdk-context",
                },
            }

            # validate if any option is used for the wrong project type
            for project_type, options in project_type_options_map.items():
                if project_type == selected_project_type:
                    continue
                for param_name, option_name in options.items():
                    if ctx.params.get(param_name) is not None and ctx.params.get(param_name) != ():
                        raise click.BadOptionUsage(
                            option_name=option_name,
                            ctx=ctx,
                            message=f"Option '{option_name}' cannot be used for Project Type '{selected_project_type}'",
                        )

            project_types_requring_stack_check = [ProjectTypes.CDK.value]
            project = kwargs.get("project")
            guided = ctx.params.get("guided", False) or ctx.params.get("g", False)
            stack_name = ctx.params.get("stack_name")
            if selected_project_type in project_types_requring_stack_check and project and require_stack and not guided:
                if ctx.params.get("stack_name") is not None:
                    if project.find_stack_by_name(stack_name) is None:
                        raise click.BadOptionUsage(
                            option_name="--stack-name",
                            ctx=ctx,
                            message=f"Stack with stack name '{stack_name}' not found.",
                        )
                elif len(project.stacks) > 1:
                    raise click.BadOptionUsage(
                        option_name="--stack-name",
                        ctx=ctx,
                        message="More than one stack found. Use '--stack-name' to specify the stack.",
                    )

            command = ctx.command.name
            if command == "deploy" and not stack_name and not guided:
                raise click.BadOptionUsage(
                    option_name="--stack-name",
                    ctx=ctx,
                    message="Missing option '--stack-name', 'sam deploy --guided' can "
                    "be used to provide and save needed parameters for future deploys.",
                )

            return func(*args, **kwargs)

        return wrapped

    return inner
