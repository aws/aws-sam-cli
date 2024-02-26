"""
Configures a logger
"""

import logging
import os
import sys

from rich.console import Console
from rich.logging import RichHandler

SAM_CLI_FORMATTER = logging.Formatter("%(message)s")
SAM_CLI_FORMATTER_WITH_TIMESTAMP = logging.Formatter("%(asctime)s | %(message)s")

SAM_CLI_LOGGER_NAME = "samcli"
LAMBDA_BULDERS_LOGGER_NAME = "aws_lambda_builders"

NO_LOGGING_COLOR_ENV_VAR = "NO_COLOR"
SAM_NO_LOGGING_COLOR_ENV_VAR = "SAM_CLI_NO_COLOR"
TERMINAL_ENV_VAR = "TERM"
DUMB_TERMINAL = "dumb"


class SamCliLogger:
    @staticmethod
    def configure_logger(logger, formatter, level):
        """
        Configure a Logger with the level provided and also the first handler's formatter.
        If there is no handler in the logger, a new StreamHandler will be added.

        Parameters
        ----------
        logger logging.getLogger
            Logger to configure
        formatter logging.formatter
            Formatter for the logger
        """
        handlers = logger.handlers
        if handlers:
            log_stream_handler = handlers[0]
        else:
            log_stream_handler = (
                RichHandler(console=Console(stderr=True), show_time=False, show_path=False, show_level=False)
                if sys.stderr.isatty()
                and not any(
                    [
                        os.getenv(NO_LOGGING_COLOR_ENV_VAR),
                        os.getenv(SAM_NO_LOGGING_COLOR_ENV_VAR),
                        os.getenv(TERMINAL_ENV_VAR) == DUMB_TERMINAL,
                    ]
                )
                else logging.StreamHandler()
            )
            logger.addHandler(log_stream_handler)
        log_stream_handler.setLevel(logging.DEBUG)
        log_stream_handler.setFormatter(formatter)

        logger.setLevel(level)
        logger.propagate = False

    @staticmethod
    def configure_null_logger(logger):
        """
        Configure a Logger with a NullHandler

        Useful for libraries that do not follow:
            https://docs.python.org/3.9/howto/logging.html#configuring-logging-for-a-library

        Parameters
        ----------
        logger logging.getLogger
            Logger to configure
        """
        logger.propagate = False
        logger.addHandler(logging.NullHandler())
