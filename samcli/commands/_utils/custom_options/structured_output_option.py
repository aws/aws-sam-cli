"""
Custom click option for the shared structured output flag
"""

import click


class StructuredOutputOption(click.Option):
    """Marks the shared --output option that selects structured (JSON) output.

    Exists so the option can be recognised by type rather than by name. Other commands, such as
    sam list and sam remote invoke, have an unrelated --output that selects a display format and
    is worth saving to a config file, while this one describes how a single run reports.
    """
