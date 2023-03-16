from unittest import TestCase
from unittest.mock import Mock

from samcli.commands._utils.custom_options.replace_help_option import ReplaceHelpSummaryOption


class TestReplaceHelpSummaryOption(TestCase):
    def test_option(self):
        rhs = ReplaceHelpSummaryOption(param_decls=("test", "--flag"), replace_help_option="replaced")
        help_summary, _ = rhs.get_help_record(ctx=Mock())
        self.assertEqual(help_summary, "replaced")
