"""
Prints the results of bottle neck calculations
"""
from typing import List
import click

from samcli.commands.check.resources.Graph import Graph


class PrintResults:
    _graph: Graph

    def __init__(self, graph: Graph):
        """
        Args:
            graph (Graph): The graph object. This is where all of the data is stored
        """
        self._graph = graph

    def print_bottle_neck_results(self):
        """
        All warning messages are printed here
        """
        click.secho("No bottleneck concerns", fg="green")
        _print_warnings(self._graph.green_warnings)
        click.secho("Minor bottleneck concerns", fg="bright_yellow")
        _print_warnings(self._graph.yellow_warnings)
        click.secho("Major bottleneck concerns", fg="bright_red")
        _print_warnings(self._graph.red_warnings)
        click.secho("Bottlenecks found", fg="bright_red")
        _print_warnings(self._graph.red_burst_warnings)


def _print_warnings(warnings: List):
    """An individual warning message gets echoed here
    Args:
        warnings (List): List of one type of warnings
    """
    for warning in warnings:
        click.echo(warning.message + "\n")
