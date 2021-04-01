"""
Module to check container based cli parameters
"""
import click


class ContainerOptions(click.Option):
    """
    Preprocessing checks for presence of --use-container flag for container based options.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if "use_container" not in opts and opts.get(self.name) is not None:
            msg = f"""\
Missing required parameter, with --{self.name.replace("_", "-")} set.

Must provide the --use-container flag in order to use --{self.name.replace("_", "-")} flag."""
            raise click.UsageError(msg)
        self.prompt = None
        return super().handle_parse_result(ctx, opts, args)
