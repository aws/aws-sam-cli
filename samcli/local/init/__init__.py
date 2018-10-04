"""
Init module to scaffold a project app from a template
"""
import logging
import os

from cookiecutter.main import cookiecutter
from cookiecutter.exceptions import CookiecutterException
from samcli.local.init.exceptions import GenerateProjectFailedError

LOG = logging.getLogger(__name__)

_init_path = os.path.dirname(__file__)
_templates = os.path.join(_init_path, 'templates')

RUNTIME_TEMPLATE_MAPPING = {
    "python3.6": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "python2.7": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "python": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "nodejs6.10": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
    "nodejs8.10": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
    "nodejs4.3": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
    "nodejs": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
    "dotnetcore2.0": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnetcore2.1": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnetcore1.0": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnetcore": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnet": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "go1.x": os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
    "go": os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
    "java8": os.path.join(_templates, "cookiecutter-aws-sam-hello-java"),
    "java": os.path.join(_templates, "cookiecutter-aws-sam-hello-java")
}


def generate_project(
        location=None, runtime="nodejs",
        output_dir=".", name='sam-sample-app', no_input=False):
    """Generates project using cookiecutter and options given

    Generate project scaffolds a project using default templates if user
    doesn't provide one via location parameter. Default templates are
    automatically chosen depending on runtime given by the user.

    Parameters
    ----------
    location: Path, optional
        Git, HTTP, Local path or Zip containing cookiecutter template
        (the default is None, which means no custom template)
    runtime: str, optional
        Lambda Runtime (the default is "nodejs", which creates a nodejs project)
    output_dir: str, optional
        Output directory where project should be generated
        (the default is ".", which implies current folder)
    name: str, optional
        Name of the project
        (the default is "sam-sample-app", which implies a project named sam-sample-app will be created)
    no_input : bool, optional
        Whether to prompt for input or to accept default values
        (the default is False, which prompts the user for values it doesn't know for baking)

    Raises
    ------
    GenerateProjectFailedError
        If the process of baking a project fails
    """

    params = {
        "template": location if location else RUNTIME_TEMPLATE_MAPPING[runtime],
        "output_dir": output_dir,
        "no_input": no_input
    }

    LOG.debug("Parameters dict created with input given")
    LOG.debug("%s", params)

    if not location and name is not None:
        params['extra_context'] = {'project_name': name, 'runtime': runtime}
        params['no_input'] = True
        LOG.debug("Parameters dict updated with project name as extra_context")
        LOG.debug("%s", params)

    try:
        LOG.debug("Baking a new template with cookiecutter with all parameters")
        cookiecutter(**params)
    except CookiecutterException as e:
        raise GenerateProjectFailedError(project=name, provider_error=e)
