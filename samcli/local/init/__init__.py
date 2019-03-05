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

RUNTIME_DEP_TEMPLATE_MAPPING = {
    "python3.7_pip": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "python3.6_pip": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "python2.7_pip": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "python_pip": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
    "ruby_bundler": os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
    "ruby2.5_bundler": os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
    "nodejs6.10_npm": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs6"),
    "nodejs8.10_npm": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
    "nodejs_npm": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
    "dotnetcore2.0_cli-package": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnetcore2.1_cli-package": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnetcore1.0_cli-package": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnetcore_cli_package": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "dotnet_cli-package": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
    "go1.x_go-get": os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
    "go_go-get": os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
    "java8_maven": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
    "java_maven": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
    "java8_gradle": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-gradle"),
    "java_gradle": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-gradle")
}

RUNTIME_DEP_MAPPING = {
    "python3.7": ["pip"],
    "python3.6": ["pip"],
    "python2.7": ["pip"],
    "python": ["pip"],
    "ruby": ["bundler"],
    "ruby2.5": ["bundler"],
    "nodejs6.10": ["npm"],
    "nodejs8.10": ["npm"],
    "nodejs": ["npm"],
    "dotnetcore2.0": ["cli-package"],
    "dotnetcore2.1": ["cli-package"],
    "dotnetcore1.0": ["cli-package"],
    "dotnetcore": ["cli-package"],
    "dotnet": ["cli-package"],
    "go1.x": ["go-get"],
    "go": ["go-get"],
    "java8": ["maven", "gradle"],
    "java": ["maven", "gradle"]
}


def generate_project(
        location=None, runtime="nodejs", dependency_manager=None,
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
    dependency_manager: str, optional
        Dependency Manager for the Lambda Runtime Project(the default is "npm" for a "nodejs" Lambda runtime)
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

    if not dependency_manager:
        dependency_manager = RUNTIME_DEP_MAPPING[runtime][0]
    try:
        template = RUNTIME_DEP_TEMPLATE_MAPPING["{}_{}".format(runtime, dependency_manager)]
    except KeyError:
        msg = "Lambda Runtime {} only supports following dependency managers: {}".format(runtime,
                                                                                         RUNTIME_DEP_MAPPING[runtime])
        raise GenerateProjectFailedError(project=name, provider_error=msg)

    params = {
        "template": location if location else template,
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
