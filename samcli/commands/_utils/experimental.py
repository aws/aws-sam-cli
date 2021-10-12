"""Experimental flag"""
import click


EXPERIMENTAL_PROMPT = """

"""


def is_experiemental():
    pass


def experimental_click_option(default):
    return click.option(
        "--capabilities",
        cls=OptionNargs,
        required=False,
        default=default,
        type=FuncParamType(func=_space_separated_list_func_type),
        help="A list of capabilities that you must specify "
        "before AWS Cloudformation can create certain stacks. Some stack templates "
        "might include resources that can affect permissions in your AWS "
        "account, for example, by creating new AWS Identity and Access Management "
        "(IAM) users. For those stacks, you must explicitly acknowledge "
        "their capabilities by specifying this parameter. The only valid values"
        "are CAPABILITY_IAM and CAPABILITY_NAMED_IAM. If you have IAM resources, "
        "you can specify either capability. If you have IAM resources with custom "
        "names, you must specify CAPABILITY_NAMED_IAM. If you don't specify "
        "this parameter, this action returns an InsufficientCapabilities error.",
    )


@parameterized_option
def experimental_option(f, default=False):
    return experimental_click_option(default)(f)


def click_experimental_option():
    pass


def prompt_experimental():
    click.confirm(EXPERIMENTAL_PROMPT, False)