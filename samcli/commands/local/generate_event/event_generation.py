"""
Generates the services and commands for selection in SAM CLI generate-event
"""

import functools

import click
from click import Group

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.options import debug_option
from samcli.lib.generated_sample_events import events
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.version_checker import check_newer_version


class ServiceCommand(Group):
    """
    Top level command that defines the service provided

    Methods
    ----------------
    get_command(self, ctx, cmd_name):
        Get the subcommand(s) under a given service name.
    list_commands(self, ctx):
        List all of the subcommands
    """

    def __init__(self, events_lib: events.Events, *args, **kwargs):
        """
        Constructor for the ServiceCommand class

        Parameters
        ----------
        events_lib: samcli.commands.local.lib.generated_sample_events.events
            The events library that allows for CLI population and substitution
        args: list
            any arguments passed in before kwargs
        kwargs: dict
            dictionary containing the keys/values used to construct the ServiceCommand
        """

        super().__init__(*args, **kwargs)
        if not events_lib:
            raise ValueError("Events library is necessary to run this command")

        self.events_lib = events_lib
        self.all_cmds = self.events_lib.event_mapping

    def get_command(self, ctx, cmd_name):
        """
        gets the subcommands under the service name

        Parameters
        ----------
        ctx : Context
            the context object passed into the method
        cmd_name : str
            the service name
        Returns
        -------
        EventTypeSubCommand:
            returns subcommand if successful, None if not.
        """

        if cmd_name not in self.all_cmds:
            return None
        return EventTypeSubCommand(self.events_lib, cmd_name, self.all_cmds[cmd_name])

    def list_commands(self, ctx):
        """
        lists the service commands available

        Parameters
        ----------
        ctx: Context
            the context object passed into the method
        Returns
        -------
        list
            returns sorted list of the service commands available
        """

        return sorted(self.all_cmds.keys())


class EventTypeSubCommand(Group):
    """
    Class that describes the commands underneath a given service type

    Methods
    ----------------
    get_command(self, ctx, cmd_name):
        Get the subcommand(s) under a given service name.
    list_commands(self, ctx):
        List all of the subcommands
    """

    TAGS = "tags"

    def __init__(self, events_lib: events.Events, top_level_cmd_name, subcmd_definition, *args, **kwargs):
        """
        constructor for the EventTypeSubCommand class

        Parameters
        ----------
        events_lib: samcli.commands.local.lib.generated_sample_events.events
            The events library that allows for CLI population and substitution
        top_level_cmd_name: string
            the service name
        subcmd_definition: dict
            the subcommands and their values underneath the service command
        args: tuple
            any arguments passed in before kwargs
        kwargs: dict
            key/value pairs passed into the constructor
        """

        super().__init__(*args, **kwargs)
        self.top_level_cmd_name = top_level_cmd_name
        self.subcmd_definition = subcmd_definition
        self.events_lib = events_lib

    def get_command(self, ctx, cmd_name):
        """
        gets the Click Commands underneath a service name

        Parameters
        ----------
        ctx: Context
            context object passed in
        cmd_name: string
            the service name
        Returns
        -------
        cmd: Click.Command
            the Click Commands that can be called from the CLI
        """

        if cmd_name not in self.subcmd_definition:
            return None
        parameters = []
        for param_name in self.subcmd_definition[cmd_name][self.TAGS].keys():
            default = self.subcmd_definition[cmd_name][self.TAGS][param_name]["default"]
            parameters.append(
                click.Option(
                    ["--{}".format(param_name)],
                    default=default,
                    help="Specify the {} name you'd like, otherwise the default = {}".format(param_name, default),
                )
            )

        command_callback = functools.partial(
            self.cmd_implementation, self.events_lib, self.top_level_cmd_name, cmd_name
        )

        cmd = click.Command(
            name=cmd_name,
            short_help=self.subcmd_definition[cmd_name]["help"],
            params=parameters,
            callback=command_callback,
        )

        cmd = configuration_option(provider=ConfigProvider(section="parameters"))(debug_option(cmd))
        return cmd

    def list_commands(self, ctx):
        """
        lists the commands underneath a particular event

        Parameters
        ----------
        ctx: Context
            the context object passed in
        Returns
        -------
        the sorted list of commands under a service
        """
        return sorted(self.subcmd_definition.keys())

    @staticmethod
    @track_command
    @check_newer_version
    def cmd_implementation(
        events_lib: events.Events, top_level_cmd_name: str, subcmd_name: str, *args, **kwargs
    ) -> str:
        """
        calls for value substitution in the event json and returns the
        customized json as a string

        Parameters
        ----------
        events_lib : events.Events
            the Events library for generating events
        top_level_cmd_name : string
            the name of the service
        subcmd_name : string
            the name of the event under the service
        args : tuple
            any arguments passed in before kwargs
        kwargs : dict
            the keys and values for substitution in the json
        Returns
        -------
        event : string
            returns the customized event json as a string
        """
        event = events_lib.generate_event(top_level_cmd_name, subcmd_name, kwargs)
        click.echo(event)
        return event


class GenerateEventCommand(ServiceCommand):
    """
    Class that brings ServiceCommand and EventTypeSubCommand into one for easy execution
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor for GenerateEventCommand class that brings together
        ServiceCommand and EventTypeSubCommand into one class

        Parameters
        ----------
        args: tuple
            any arguments passed in before kwargs
        kwargs: dict
            commands, subcommands, and parameters for generate-event
        """
        super().__init__(events.Events(), *args, **kwargs)
