from logging import warn
import click


class PrintResults:
    def __init__(self, graph):
        self.graph = graph

    def print_bottle_neck_results(self):
        print("GREEN WARNINGS")
        self.print_warnings(self.graph.get_green_warnings())
        print("YELLOW WARNINGS")
        self.print_warnings(self.graph.get_yellow_warnings())
        print("RED WARNINGS")
        self.print_warnings(self.graph.get_red_warnings())
        print("RED BURST WARNINGS")
        self.print_warnings(self.graph.get_red_burst_warnings())

    def print_warnings(self, warnings):
        for warning in warnings:
            click.echo(warning.get_message())
