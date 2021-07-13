"""
Package command options validations util
"""
import click


def validate_and_get_project_stack(project, ctx):
    """
    Util to validate the stack to be packaged
    it checks if the project contains only one stack,
    or the stack-name option should be provided
    """
    guided = ctx.params.get("guided", False) or ctx.params.get("g", False)
    if len(project.stacks) == 1:
        stack = project.stacks[0]
    else:
        stack_name = ctx.params.get("stack_name")
        if stack_name is None and not guided:
            raise click.BadOptionUsage(
                option_name="--stack-name",
                ctx=ctx,
                message="You must specify stack name via --stack-name as your project contains more than one " "stack.",
            )
        stack = project.find_stack_by_name(stack_name)
    return stack
