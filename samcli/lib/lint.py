from typing import List, Optional, Tuple


def get_lint_matches(template: str, debug: Optional[bool] = None, region: Optional[str] = None) -> Tuple[List, str]:
    """
    Parses provided SAM template and maps errors from CloudFormation template back to SAM template.

    Cfn-lint loggers are added to the SAM cli logging hierarchy which at the root logger
    configures with INFO level logging and a different formatting. This exposes and duplicates
    some cfn-lint logs that are not typically shown to customers. Explicitly setting the level to
    WARNING and propagate to be False remediates these issues.

    Parameters
    -----------
    ctx
        Click context object
    template
        Path to the template file

    """

    import logging

    import cfnlint.core  # type: ignore

    from samcli.commands.exceptions import UserException

    cfn_lint_logger = logging.getLogger("cfnlint")
    cfn_lint_logger.propagate = False

    try:
        lint_args = [template]
        if debug:
            lint_args.append("--debug")
        if region:
            lint_args.append("--region")
            lint_args.append(region)

        (args, filenames, formatter) = cfnlint.core.get_args_filenames(lint_args)
        cfn_lint_logger.setLevel(logging.WARNING)
        matches = list(cfnlint.core.get_matches(filenames, args))
        if not matches:
            return matches, ""

        rules = cfnlint.core.get_used_rules()
        matches_output = formatter.print_matches(matches, rules, filenames)
        return matches, matches_output

    except cfnlint.core.InvalidRegionException as e:
        raise UserException(
            "AWS Region was not found. Please configure your region through the --region option",
            wrapped_from=e.__class__.__name__,
        ) from e
    except cfnlint.core.CfnLintExitException as lint_error:
        raise UserException(
            lint_error,
            wrapped_from=lint_error.__class__.__name__,
        ) from lint_error
