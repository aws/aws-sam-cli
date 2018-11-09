
import os
import click

_TEMPLATE_OPTION_DEFAULT_VALUE = "template.[yaml|yml]"


def get_or_default_template_file_name(ctx, param, provided_value):
    """
    Default value for the template file name option is more complex than what Click can handle.
    This method either returns user provided file name or one of the two default options (template.yaml/template.yml)
    depending on the file that exists

    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click. It could either be the default value or provided by user.
    :return: Actual value to be used in the CLI
    """

    if provided_value == _TEMPLATE_OPTION_DEFAULT_VALUE:
        # Default value was used. Value can either be template.yaml or template.yml. Decide based on which file exists
        # .yml is the default, even if it does not exist.
        provided_value = "template.yml"

        option = "template.yaml"
        if os.path.exists(option):
            provided_value = option

    return os.path.abspath(provided_value)


def template_common_option(f):
    """
    Common ClI option for template

    :param f: Callback passed by Click
    :return: Callback
    """
    return template_click_option()(f)


def template_click_option():
    """
    Click Option for template option
    """
    return click.option('--template', '-t',
                        default=_TEMPLATE_OPTION_DEFAULT_VALUE,
                        type=click.Path(),
                        envvar="SAM_TEMPLATE_FILE",
                        callback=get_or_default_template_file_name,
                        show_default=True,
                        help="AWS SAM template file")
