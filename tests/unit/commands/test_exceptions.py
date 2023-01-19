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

        self.assertIn("Error:", output)
        self.assertIn("Traceback:", output)
        self.assertIn('raise Exception("my_exception")', output)
        self.assertIn(
            'An unexpected error was encountered while executing "test_command".\n'
            "Search for an existing issue:\n"
            "https://github.com/aws/aws-sam-cli/issues?q=is%3Aissue+is%3Aopen+Bug%3A%20test_command%20-%20Exception\n"
            "Or create a bug report:\n"
            "https://github.com/aws/aws-sam-cli/issues/new?template=Bug_report.md&title=Bug%3A%20test_command%20-%20Exception",
            output,
        )
