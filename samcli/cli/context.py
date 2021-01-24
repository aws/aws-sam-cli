"""
Context information passed to each CLI command
"""

import logging
import uuid
from typing import Optional, cast

import boto3
import botocore
import botocore.session
from botocore import credentials
import click

from samcli.commands.exceptions import CredentialsError
from samcli.lib.utils.sam_logging import (
    LAMBDA_BULDERS_LOGGER_NAME,
    SamCliLogger,
    SAM_CLI_FORMATTER_WITH_TIMESTAMP,
    SAM_CLI_LOGGER_NAME,
)


class Context:
    """
    Top level context object for the CLI. Exposes common functionality required by a CLI, including logging,
    environment config parsing, debug logging etc.

    This object is passed by Click to every command that adds the proper annotation.
    Read this for more details on Click Context - http://click.pocoo.org/5/commands/#nested-handling-and-contexts
    Each command gets its own context object, but linked to both parent and child command's context, like a Linked List.

    This class itself does not rely on how Click works. It is just a plain old Python class that holds common
    properties used by every CLI command.
    """

    _session_id: str

    def __init__(self):
        """
        Initialize the context with default values
        """
        self._debug = False
        self._aws_region = None
        self._aws_profile = None
        self._session_id = str(uuid.uuid4())

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, value):
        """
        Turn on debug logging if necessary.

        :param value: Value of debug flag
        """
        self._debug = value

        if self._debug:
            # Turn on debug logging and display timestamps
            sam_cli_logger = logging.getLogger(SAM_CLI_LOGGER_NAME)
            lambda_builders_logger = logging.getLogger(LAMBDA_BULDERS_LOGGER_NAME)
            SamCliLogger.configure_logger(sam_cli_logger, SAM_CLI_FORMATTER_WITH_TIMESTAMP, logging.DEBUG)
            SamCliLogger.configure_logger(lambda_builders_logger, SAM_CLI_FORMATTER_WITH_TIMESTAMP, logging.DEBUG)

    @property
    def region(self):
        return self._aws_region

    @region.setter
    def region(self, value):
        """
        Set AWS region
        """
        self._aws_region = value
        self._refresh_session()

    @property
    def profile(self):
        return self._aws_profile

    @profile.setter
    def profile(self, value):
        """
        Set AWS profile for credential resolution
        """
        self._aws_profile = value
        self._refresh_session()

    @property
    def session_id(self) -> str:
        """
        Returns the ID of this command session. This is a randomly generated UUIDv4 which will not change until the
        command terminates.
        """
        return self._session_id

    @property
    def command_path(self):
        """
        Returns the full path of the command as invoked ex: "sam local generate-event s3 put". Wrapper to
        https://click.palletsprojects.com/en/7.x/api/#click.Context.command_path

        Returns
        -------
        str
            Full path of the command invoked
        """

        # Uses Click's Core Context. Note, this is different from this class, also confusingly named `Context`.
        # Click's Core Context object is the one that contains command path information.
        click_core_ctx = click.get_current_context()
        if click_core_ctx:
            return click_core_ctx.command_path

        return None

    @property
    def template_dict(self):
        """
        Returns the template_dictionary from click context.
        Returns
        -------
        dict
            Template as dictionary

        """
        click_core_ctx = click.get_current_context()
        if click_core_ctx:
            return click_core_ctx.template_dict

        return None

    @staticmethod
    def get_current_context() -> Optional["Context"]:
        """
        Get the current Context object from Click's context stacks. This method is safe to run within the
        actual command's handler that has a ``@pass_context`` annotation. Outside of the handler, you run
        the risk of creating a new Context object which is entirely different from the Context object used by your
        command.
         .. code:
            @pass_context
            def my_command_handler(ctx):
                 # You will get the right context from within the command handler. This will also work from any
                # downstream method invoked as part of the handler.
                 this_context = Context.get_current_context()
                assert ctx == this_context
         Returns
        -------
        samcli.cli.context.Context
            Instance of this object, if we are running in a Click command. None otherwise.
        """

        # Click has the concept of Context stacks. Think of them as linked list containing custom objects that are
        # automatically accessible at different levels. We start from the Core Click context and discover the
        # SAM CLI command-specific Context object which contains values for global options used by all commands.
        #
        # https://click.palletsprojects.com/en/7.x/complex/#ensuring-object-creation
        #

        click_core_ctx = click.get_current_context()
        if click_core_ctx:
            return cast("Context", click_core_ctx.find_object(Context) or click_core_ctx.ensure_object(Context))

        return None

    def _refresh_session(self):
        """
        Update boto3's default session by creating a new session based on values set in the context. Some properties of
        the Boto3's session object are read-only. Therefore when Click parses new AWS session related properties (like
        region & profile), it will call this method to create a new session with latest values for these properties.
        """
        try:
            botocore_session = botocore.session.get_session()
            boto3.setup_default_session(
                botocore_session=botocore_session, region_name=self._aws_region, profile_name=self._aws_profile
            )
            # get botocore session and setup caching for MFA based credentials
            botocore_session.get_component("credential_provider").get_provider(
                "assume-role"
            ).cache = credentials.JSONFileCache()

        except botocore.exceptions.ProfileNotFound as ex:
            raise CredentialsError(str(ex)) from ex


def get_cmd_names(cmd_name, ctx):
    """
    Given the click core context, return a list representing all the subcommands passed to the CLI

    Parameters
    ----------
    cmd_name : name of current command

    ctx : click.Context

    Returns
    -------
    list(str)
        List containing subcommand names. Ex: ["local", "start-api"]

    """
    if not ctx:
        return []

    if ctx and not getattr(ctx, "parent", None):
        return [ctx.info_name]
    # Find parent of current context
    _parent = ctx.parent
    _cmd_names = []
    # Need to find the total set of commands that current command is part of.
    if cmd_name != ctx.info_name:
        _cmd_names = [cmd_name]
    _cmd_names.append(ctx.info_name)
    # Go through all parents till a parent of a context exists.
    while _parent.parent:
        info_name = _parent.info_name
        _cmd_names.append(info_name)
        _parent = _parent.parent

    # Make sure the output reads natural. Ex: ["local", "start-api"]
    _cmd_names.reverse()
    return _cmd_names
