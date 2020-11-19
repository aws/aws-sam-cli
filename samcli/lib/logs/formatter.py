"""
Format log events produced by CloudWatch Logs
"""

import json
import functools


class LogsFormatter:
    """
    Formats log messages returned by CloudWatch Logs service.
    """

    def __init__(self, colored, formatter_chain=None):
        """

        ``formatter_chain`` is a list of methods that can format an event. Each method must take an
        ``samcli.lib.logs.event.LogEvent`` object as input and return the same object back. This allows us to easily
        chain formatter methods one after another. This class will apply all the formatters from this list on each
        log event.

        After running the formatter chain, this class will convert the event object to string by appending
        the timestamp to message. To skip all custom formatting and simply convert event to string, you can leave
        the ``formatter_chain`` list empty.

        Formatter Method
        ================
        Formatter method needs to accept two arguments at a minimum: ``event`` and ``colored``. It can make
        modifications to the contents of ``event`` and must return the same object.

        Example:
        .. code-block:: python

            def my_formatter(event, colored):
                \"""
                Example of a custom log formatter

                Parameters
                ----------
                event : samcli.lib.logs.event.LogEvent
                    Log event to format

                colored : samcli.lib.utils.colors.Colored
                    Instance of ``Colored`` object to add colors to the message

                Returns
                -------
                samcli.lib.logs.event.LogEvent
                    Object representing the log event that has been formatted. It could be the same event object passed
                    via input.
                \"""

                # Do your formatting

                return event

        Parameters
        ----------
        colored : samcli.lib.utils.colors.Colored
            Used to add color to the string when pretty printing. Colors are useful only when pretty printing on a
            Terminal. To turn off coloring, set the appropriate property when instantiating the
            ``samcli.lib.utils.colors.Colored`` class.

        formatter_chain : list of formatter methods

        """

        self.colored = colored
        self.formatter_chain = formatter_chain or []

        # At end of the chain, pretty print the Event object as string.
        self.formatter_chain.append(LogsFormatter._pretty_print_event)

    def do_format(self, event_iterable):
        """
        Formats the given CloudWatch Logs Event dictionary as necessary and returns an iterable that will
        return the formatted string. This can be used to parse and format the events based on context
        ie. In Lambda Function logs, a formatter may wish to color the "ERROR" keywords red,
        or highlight a filter keyword separately etc.

        This method takes an iterable as input and returns an iterable. It does not immediately format the event.
        Instead, it sets up the formatter chain appropriately and returns the iterable. Actual formatting happens
        only when the iterable is used by the caller.

        Parameters
        ----------
        event_iterable : iterable of samcli.lib.logs.event.LogEvent
            Iterable that returns an object containing information about each log event.

        Returns
        -------
        iterable of string
            Iterable that returns a formatted event as a string.
        """

        for operation in self.formatter_chain:

            # Make sure the operation has access to certain basic objects like colored
            partial_op = functools.partial(operation, colored=self.colored)
            event_iterable = map(partial_op, event_iterable)

        return event_iterable

    @staticmethod
    def _pretty_print_event(event, colored):
        """
        Basic formatter to convert an event object to string
        """
        event.timestamp = colored.yellow(event.timestamp)
        event.log_stream_name = colored.cyan(event.log_stream_name)

        return " ".join([event.log_stream_name, event.timestamp, event.message])


class LambdaLogMsgFormatters:
    """
    Format logs printed by AWS Lambda functions.

    This class is a collection of static methods that can be used within a formatter chain.
    """

    @staticmethod
    def colorize_errors(event, colored):
        """
        Highlights some commonly known Lambda error cases in red:
            - Nodejs process crashes
            - Lambda function timeouts
        """

        nodejs_crash_msg = "Process exited before completing request"
        timeout_msg = "Task timed out"

        if nodejs_crash_msg in event.message or timeout_msg in event.message:
            event.message = colored.red(event.message)

        return event


class KeywordHighlighter:
    """
    Highlight certain keywords in the log line
    """

    def __init__(self, keyword=None):
        self.keyword = keyword

    def highlight_keywords(self, event, colored):
        """
        Highlight the keyword in the log statement by drawing an underline
        """
        if self.keyword:
            highlight = colored.underline(self.keyword)
            event.message = event.message.replace(self.keyword, highlight)

        return event


class JSONMsgFormatter:
    """
    Pretty print JSONs within a message
    """

    @staticmethod
    def format_json(event, colored):
        """
        If the event message is a JSON string, then pretty print the JSON with 2 indents and sort the keys. This makes
        it very easy to visually parse and search JSON data
        """

        try:
            if event.message.startswith("{"):
                msg_dict = json.loads(event.message)
                event.message = json.dumps(msg_dict, indent=2)
        except Exception:
            # Skip if the event message was not JSON
            pass

        return event
