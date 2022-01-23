DESIGN DOCUMENT
===============

> \"..with proper design, the features come cheaply \" - Dennis Ritchie

This document is intended to capture key decisions in the design of this
CLI. This is especially useful for new contributors to understand the
codebase and keep the changes aligned with design decisions. We will
update this document when new components are added or the CLI design
changes significantly.

Tenets
======

These are some key guiding principles for the design:

-   Extensibility is by design. It is not an after thought.
-   Each component must be self-contained and testable in isolation.
-   Command line interface must be one of many supported input
    mechanisms.
-   SAM is one of many supported input formats.

CLI Framework
=============

This component implements generic CLI functionality that makes it easy
to write individual CLI commands. It performs:

-   CLI argument parsing
-   Generating help text and man pages from RST docs of the command.
-   Fetching configuration information from environment
-   Consistent exit code generation
-   [Future] HTTP Mode: Ability to call the CLI commands with same
    parameters through a HTTP Endpoint. This is useful for IDEs and
    other tools to integrate with this CLI.

Each command, along with any subcommands, is implemented using Click
annotations. They are not directly wired with the core of the CLI.
Instead, commands are dynamically loaded into the CLI at run time by
importing the Python package implementing the command. For example,
assuming two commands are implemented at Python packages
``foo.cli.cmd1`` and ``foo.cli.cmd2``, then the CLI framework will
dynamically import these two packages and connect them to parent Click
instance. The CLI framework expects the command's Click object to be
exposed through an attribute called `cli`.

For example: if ``foo.bar.hello`` is the package where ``hello`` command
is implemented, then ``/foo/bar/hello/__init__.py`` file is expected
to contain a Click object called `cli`.

By convention, the name of last module in the package's name is the
command's name. ie. A package of ``foo.bar.baz`` will produce a command
name ``baz``.

Commands that make up of the core functionality (like local, validate,
generate-event etc) are also implemented this way. They are baked into
the CLI, but in the future, we will provide options to completely remove
a command.

By convention, each command is implemented as a separate Python package
where the `__init__.py` file exposes the `cli` attribute. This allows
new commands to be built and distributed as Python packages through PIP,
opening the architecture to support plugins in future. This structure
also forces commands implementations to be modular, reusable, and highly
customizable. When RC files are implemented, new commands can be added
or existing commands can be removed, with simple a configuration in the
RC file.

Internal Environment Variables
==============================

SAM CLI uses the following internal, undocumented, environment variables
for development purposes. They should *not* be used by customers:

- `__SAM_CLI_APP_DIR`: Path to application directory to be used in place
   of `~/.aws-sam` directory. 
   
- `__SAM_CLI_TELEMETRY_ENDPOINT_URL`: HTTP Endpoint where the Telemetry 
  metrics will be published to
