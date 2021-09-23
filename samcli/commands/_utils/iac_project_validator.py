"""
Provide IacProjectValidator to validate IaC project information from command line options
"""
import logging

import click
from click import Context

from samcli.commands._utils.exceptions import PackageResolveS3AndS3SetError, PackageResolveS3AndS3NotSetError
from samcli.commands._utils.option_validator import Validator
from samcli.lib.iac.interface import ProjectTypes, Project
from samcli.lib.utils.packagetype import ZIP, IMAGE

LOG = logging.getLogger(__name__)


class IacProjectValidator:
    def __init__(self, click_ctx: Context, project: Project):
        self._ctx = click_ctx
        self._params = click_ctx.params
        self._command_path = click_ctx.command_path
        self._project = project

    def iac_options_validation(self, require_stack=False):
        """
        Validation function that will run after cli parameters have been loaded
        and iac plugin has been injected. Validations vary based on project type.

        :param require_stack: a boolean flag to set whether --stack-name is required or not
        """

        selected_project_type = self._params.get("project_type")

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
                if self._params.get(param_name) is not None and self._params.get(param_name) != ():
                    raise click.BadOptionUsage(
                        option_name=option_name,
                        ctx=self._ctx,
                        message=f"Option '{option_name}' cannot be used for Project Type '{selected_project_type}'",
                    )

        project_types_requring_stack_check = [ProjectTypes.CDK.value]
        guided = self._params.get("guided", False) or self._params.get("g", False)
        stack_name = self._params.get("stack_name")
        if self._project and require_stack and not guided:
            # Check if the stack name is defined if the project (e.g. CDK project) needs a stack name
            # Fail the validation if:
            # 1. The "--stack-name" is not defined and there is more than one stack in the project
            # 2. The "--stack-name" is defined, but the stack doesn't exist in the project.
            if selected_project_type in project_types_requring_stack_check:
                if stack_name is not None:
                    if self._project.find_stack_by_name(stack_name) is None:
                        raise click.BadOptionUsage(
                            option_name="--stack-name",
                            ctx=self._ctx,
                            message=f"Stack with stack name '{stack_name}' not found.",
                        )
                elif len(self._project.stacks) > 1:
                    raise click.BadOptionUsage(
                        option_name="--stack-name",
                        ctx=self._ctx,
                        message="More than one stack found. Use '--stack-name' to specify the stack.",
                    )
            # "sam deploy" specific: fail validation if "--stack-name" is not given in "sam deploy" unguided mode.
            command_path = (
                self._command_path.split(" ", 1)[-1]
                if len(self._command_path.split(" ", 1)) > 1
                else self._command_path
            )
            if command_path == "deploy" and not stack_name:
                raise click.BadOptionUsage(
                    option_name="--stack-name",
                    ctx=self._ctx,
                    message="Missing option '--stack-name', 'sam deploy --guided' can "
                    "be used to provide and save needed parameters for future deploys.",
                )

    def package_option_validation(self):
        """
        Validation function specific to package options.
        """
        stack = validate_and_get_project_stack(self._project, self._ctx)

        # NOTE(sriram-mv): Both params and default_map need to be checked, as the option can be either be
        # passed in directly or through configuration file.
        # If passed in through configuration file, default_map is loaded with those values.
        guided = self._params.get("guided", False) or self._params.get("g", False)
        resolve_s3_provided = self._params.get("resolve_s3", False) or self._ctx.default_map.get("resolve_s3", False)
        s3_bucket_provided = self._params.get("s3_bucket", False) or self._ctx.default_map.get("s3_bucket", False)
        either_required = stack.has_assets_of_package_type(ZIP) if stack is not None else False
        if not guided and s3_bucket_provided and resolve_s3_provided:
            raise PackageResolveS3AndS3SetError()
        if not guided and either_required and not s3_bucket_provided and not resolve_s3_provided:
            raise PackageResolveS3AndS3NotSetError()

    def image_repository_validation(self):
        """
        Validation function to check for conditions surrounding `--image-repository` and `--image-repositories`. The
        reason they are done last instead of in callback functions, is because the options depend on each other, and
        this breaks cyclic dependencies.
        """

        guided = self._params.get("guided", False) or self._params.get("g", False)
        image_repository = self._params.get("image_repository", False)
        image_repositories = self._params.get("image_repositories", False) or {}
        stack = validate_and_get_project_stack(self._project, self._ctx)

        # Check if `--image-repository` or `--image-repositories` are required by
        # looking for resources that have an IMAGE based packagetype.
        required = stack.has_assets_of_package_type(IMAGE) if stack is not None else False

        validators = [
            Validator(
                validation_function=lambda: image_repository and image_repositories,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=self._ctx,
                    message="Both '--image-repositories' and '--image-repository' cannot be provided. "
                    "Do you have both specified in the command or in a configuration file?",
                ),
            ),
            Validator(
                validation_function=lambda: not guided and not (image_repository or image_repositories) and required,
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=self._ctx,
                    message="Missing option '--image-repository' or '--image-repositories'",
                ),
            ),
            Validator(
                validation_function=lambda: not guided
                and (
                    set(image_repositories.keys())
                    != set(map(lambda r: r.item_id, stack.find_function_resources_of_package_type(IMAGE)))
                    and image_repositories
                ),
                exception=click.BadOptionUsage(
                    option_name="--image-repositories",
                    ctx=self._ctx,
                    message="Incomplete list of function logical ids specified for '--image-repositories'",
                ),
            ),
        ]
        for validator in validators:
            validator.validate()
        # Call Original function after validation.


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
