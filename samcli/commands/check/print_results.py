from logging import warn
import click


class PrintResults:
    def __init__(self, graph, lambda_pricing_results):
        self.graph = graph
        self.lambda_pricing_results = lambda_pricing_results

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
        for warning in warnings:
            click.echo(warning.get_message() + "\n")

    def print_all_pricing_results(self):
        click.echo("With the current resource allocation, we estimate the following costs:")
        click.echo("\t* AWS Lambda: $%.2f/month" % self.lambda_pricing_results)

        click.echo("\t------------------")
        click.echo("\t Total: $%.2f/month" % self.lambda_pricing_results)
