"""
Custom click option for customizing help text.
"""

import click

from samcli.lib.utils.colors import Colored


class RequiredOptionColorTextOption(click.Option):
    def __init__(self, *args, **kwargs):
        super(RequiredOptionColorTextOption, self).__init__(*args, **kwargs)
        self.colored = Colored()

    def get_help_record(self, ctx):
        option, help_text = super(RequiredOptionColorTextOption, self).get_help_record(ctx=ctx)
        return (self.colored.yellow(option), self.colored.yellow(help_text)) if self.required else (option, help_text)


class ReplaceHelpSummaryOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.replace_help_option = kwargs.get("replace_help_option", "")
        kwargs.pop("replace_help_option")
        super(ReplaceHelpSummaryOption, self).__init__(*args, **kwargs)

    def get_help_record(self, ctx):
        option, help_text = super(ReplaceHelpSummaryOption, self).get_help_record(ctx=ctx)
        return self.replace_help_option, help_text
