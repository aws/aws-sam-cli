"""
Prints the results of bottle neck calculations
"""
from typing import List
import click

from samcli.commands.check.resources.Graph import Graph


class PrintResults:
    def __init__(self, graph: Graph):
        self._graph = graph

    def print_bottle_neck_results(self):
        click.secho("No bottleneck concerns", fg="green")
        _print_warnings(self._graph.green_warnings)
        click.secho("Minor bottleneck concerns", fg="bright_yellow")
        _print_warnings(self._graph.yellow_warnings)
        click.secho("Major bottleneck concerns", fg="bright_red")
        _print_warnings(self._graph.red_warnings)
        click.secho("Bottlenecks found", fg="bright_red")
        _print_warnings(self._graph.red_burst_warnings)


def _print_warnings(warnings: List):
    for warning in warnings:
        click.echo(warning.message + "\n")
