"""
ProgressBar operations
"""

import click


def progressbar(length, label):  # type: ignore[no-untyped-def]
    """
    Creates a progressbar

    Parameters
    ----------
    length int
        Length of the ProgressBar
    label str
        Label to give to the progressbar

    Returns
    -------
    click.progressbar
        Progressbar

    """
    return click.progressbar(length=length, label=label, show_pos=True)
