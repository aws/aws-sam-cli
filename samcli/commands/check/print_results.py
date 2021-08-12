"""
Prints the results of bottle neck calculations
"""
from typing import List
import click

from samcli.commands.check.resources.graph import CheckGraph
from samcli.commands.check.resources.warning import CheckWarning


class CheckResults:
    _graph: CheckGraph
    _lambda_pricing_results: float

    def __init__(self, graph: CheckGraph, lambda_pricing_results: float):
        self._graph = graph
        self._lambda_pricing_results = lambda_pricing_results

    def print_bottle_neck_results(self) -> None:
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

    def print_all_pricing_results(self) -> None:
        """
        Prints the pricing results for all individual resources
        (excluding lambda functions). The  it prints the pricing results for all
        resources of the same type. Then it prints the pricing results for
        the entire application.
        """
        click.echo("With the current resource allocation, we estimate the following costs:")
        click.echo("\t* AWS Lambda: $%.2f/month" % self._lambda_pricing_results)

        click.echo("\t------------------")
        click.echo("\t Total: $%.2f/month" % self._lambda_pricing_results)


def _print_warnings(warnings: List[CheckWarning]) -> None:
    """An individual warning message gets echoed here
    Parameters
    ----------
        warnings: List[CheckWarning]
            List of one type of warnings
    """
    for warning in warnings:
        click.echo(warning.message + "\n")
