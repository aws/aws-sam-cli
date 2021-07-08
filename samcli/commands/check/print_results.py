from logging import warn
import click


class PrintResults:
    def __init__(self, graph):
        self.graph = graph

    def print_bottle_neck_results(self):
        click.secho("No bottleneck concerns", fg="green")
        self.print_warnings(self.graph.get_green_warnings())
        click.secho("Minor bottleneck concerns", fg="bright_yellow")
        self.print_warnings(self.graph.get_yellow_warnings())
        click.secho("Major bottleneck concerns", fg="bright_red")
        self.print_warnings(self.graph.get_red_warnings())
        click.secho("Bottlenecks found", fg="bright_red")
        self.print_warnings(self.graph.get_red_burst_warnings())

    def print_warnings(self, warnings):
        for wawa in warnings:
            click.echo(wawa.get_message() + "\n")
