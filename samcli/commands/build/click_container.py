"""
Module to check container based cli parameters
"""
import click


class ContainerOptions(click.Option):
    """
    Preprocessing checks for presence of --use-container flag for container based options.
    """

    def handle_parse_result(self, ctx, opts, args):
        if "use_container" not in opts and self.name in opts:
            opt_name = self.name.replace("_", "-")
            msg = f"Missing required parameter, need the --use-container flag in order to use --{opt_name} flag."
            raise click.UsageError(msg)
        # To make sure no user input prompting happens
        self.prompt = None
        return super().handle_parse_result(ctx, opts, args)
