"""
Common CLI options shared by various commands
"""

import click


def stack_name_click_option():
    return click.option(
        "--stack-name",
        help=(
            "Name of corresponding deployed stack.(Not including "
            "a stack name will only show local resources defined "
            "in the template.) "
        ),
        type=click.STRING,
    )


def stack_name_option(f):
    return stack_name_click_option()(f)


def output_click_option():
    return click.option(
        "--output",
        help=(
            "Output the results from the command in a given " 
            "output format (json, yaml, table or text). "
        ),
        type=click.Choice(["json", "table"], case_sensitive=False),
    )


def output_option(f):
    return output_click_option()(f)
