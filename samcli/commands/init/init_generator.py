import click

from samcli.commands.exceptions import UserException
from samcli.local.init import generate_project
from samcli.local.init.exceptions import GenerateProjectFailedError


def do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context):
    no_build_msg = """
Project generated: {output_dir}/{name}

Steps you can take next within the project folder
===================================================
[*] Invoke Function: sam local invoke HelloWorldFunction --event event.json
[*] Start API Gateway locally: sam local start-api
""".format(
        output_dir=output_dir, name=name
    )

    build_msg = """
Project generated: {output_dir}/{name}

Steps you can take next within the project folder
===================================================
[*] Install dependencies
[*] Invoke Function: sam local invoke HelloWorldFunction --event event.json
[*] Start API Gateway locally: sam local start-api
""".format(
        output_dir=output_dir, name=name
    )

    no_build_step_required = (
        "python",
        "python3.7",
        "python3.6",
        "python2.7",
        "nodejs",
        "nodejs4.3",
        "nodejs6.10",
        "nodejs8.10",
        "nodejs10.x",
        "ruby2.5",
    )
    next_step_msg = no_build_msg if runtime in no_build_step_required else build_msg
    try:
        generate_project(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
        if not location:
            click.secho(next_step_msg, bold=True)
            click.secho("Read {name}/README.md for further instructions\n".format(name=name), bold=True)
            click.secho("[*] Project initialization is now complete", fg="green")
    except GenerateProjectFailedError as e:
        raise UserException(str(e))
