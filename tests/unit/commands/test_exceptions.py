import io

from unittest import TestCase
from unittest.mock import patch, Mock


from samcli.commands.exceptions import UnhandledException


class TestUnhandledException(TestCase):
    def test_show_must_print_traceback_and_message(self):
        wrapped_exception = None
        try:
            raise Exception("my_exception")
        except Exception as e:
            wrapped_exception = e

        unhandled_exception = UnhandledException("test_command", wrapped_exception)
        f = io.StringIO()
        unhandled_exception.show(f)

        output = f.getvalue()

        self.assertIn("Traceback:", output)
        self.assertIn('raise Exception("my_exception")', output)
        self.assertIn(
            'An unexpected error was encountered while executing "test_command".\n'
            "To create a bug report, follow the Github issue template below:\n"
            "https://github.com/aws/aws-sam-cli/issues/new?template=Bug_report.md&title=test_command%20-%20Exception",
            output,
        )
