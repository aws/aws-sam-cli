"""
ProgressBar operations
"""

import click


def progressbar(length, label):
    """Creates a progressbar

    Parameters
    ----------
    length int :
        Length of the ProgressBar
    label str :
        Label to give to the progressbar
    length :

    label :


    Returns
    -------


    """
    return click.progressbar(length=length, label=label, show_pos=True)
