"""
Option validations for Package command
Use as decorator and place the decorator after:
1. all CLI options have been processed.
2. iac plugin has been injected
"""
import functools
import logging

import click
from samcli.commands.package.exceptions import PackageResolveS3AndS3NotSetError, PackageResolveS3AndS3SetError
from samcli.commands.package.utils import validate_and_get_project_stack
from samcli.lib.utils.packagetype import ZIP

LOG = logging.getLogger(__name__)


def package_option_validation(func):
    """
    Wrapper validation function that will run after cli parameters have been loaded
    and iac plugin has been injected.
    """

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        project = kwargs.get("project")
        ctx = click.get_current_context()
        stack = validate_and_get_project_stack(project, ctx)

        # NOTE(sriram-mv): Both params and default_map need to be checked, as the option can be either be
        # passed in directly or through configuration file.
        # If passed in through configuration file, default_map is loaded with those values.
        guided = ctx.params.get("guided", False) or ctx.params.get("g", False)
        resolve_s3_provided = ctx.params.get("resolve_s3", False) or ctx.default_map.get("resolve_s3", False)
        s3_bucket_provided = ctx.params.get("s3_bucket", False) or ctx.default_map.get("s3_bucket", False)
        either_required = stack.has_assets_of_package_type(ZIP) if stack is not None else False
        if not guided and s3_bucket_provided and resolve_s3_provided:
            raise PackageResolveS3AndS3SetError()
        if not guided and either_required and not s3_bucket_provided and not resolve_s3_provided:
            raise PackageResolveS3AndS3NotSetError()

        return func(*args, **kwargs)

    return wrapped
