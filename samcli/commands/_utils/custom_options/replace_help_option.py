"""
Click option for replacing help text option name.
"""

import click


class ReplaceHelpSummaryOption(click.Option):
    def __init__(self, *args, **kwargs):
        self.replace_help_option = kwargs.pop("replace_help_option", "")
        super(ReplaceHelpSummaryOption, self).__init__(*args, **kwargs)

    def get_help_record(self, ctx):
        help_record, help_text = super(ReplaceHelpSummaryOption, self).get_help_record(ctx=ctx)
        return self.replace_help_option if self.replace_help_option else help_record, help_text
