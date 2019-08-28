"""
Configures a logger
"""
import logging


class SamCliLogger(object):
    @staticmethod
    def configure_logger(logger, formatter, level):
        """
        Configure a Logger with the formatter provided.

        Parameters
        ----------
        logger logging.getLogger
            Logger to configure
        formatter logging.formatter
            Formatter for the logger

        Returns
        -------
        None
        """
        log_stream_handler = logging.StreamHandler()
        log_stream_handler.setLevel(logging.DEBUG)
        log_stream_handler.setFormatter(formatter)

        logger.setLevel(level)
        logger.propagate = False
        logger.addHandler(log_stream_handler)
