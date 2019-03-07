"""
Init module to scaffold a project app from a template
"""
import itertools
import logging

from cookiecutter.exceptions import CookiecutterException
from cookiecutter.main import cookiecutter

from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING
from samcli.local.init.exceptions import GenerateProjectFailedError

LOG = logging.getLogger(__name__)


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

    template = None

    for mapping in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values()))):
        if runtime in mapping['runtimes'] or any([r.startswith(runtime) for r in mapping['runtimes']]):
            if not dependency_manager:
                template = mapping['init_location']
                break
            elif dependency_manager == mapping['dependency_manager']:
                template = mapping['init_location']

    if not template:
        msg = "Lambda Runtime {} does not support dependency manager: {}".format(runtime, dependency_manager)
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
