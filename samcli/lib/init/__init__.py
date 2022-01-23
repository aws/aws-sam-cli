"""
Init module to scaffold a project app from a template
"""
import itertools
import logging
import platform

from pathlib import Path

from cookiecutter.exceptions import CookiecutterException, RepositoryNotFound, UnknownRepoType
from cookiecutter.main import cookiecutter

from samcli.local.common.runtime_template import RUNTIME_DEP_TEMPLATE_MAPPING
from samcli.lib.utils.packagetype import ZIP
from samcli.lib.utils import osutils
from .exceptions import GenerateProjectFailedError, InvalidLocationError
from .arbitrary_project import generate_non_cookiecutter_project

LOG = logging.getLogger(__name__)


def generate_project(
    location=None,
    package_type=None,
    runtime=None,
    dependency_manager=None,
    output_dir=".",
    name=None,
    no_input=False,
    extra_context=None,
):
    """Generates project using cookiecutter and options given

    Generate project scaffolds a project using default templates if user
    doesn't provide one via location parameter. Default templates are
    automatically chosen depending on runtime given by the user.

    Parameters
    ----------
    location: Path, optional
        Git, HTTP, Local path or Zip containing cookiecutter template
        (the default is None, which means no custom template)
    package_type : Optional[str]
        Optional string representing the package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
    runtime: str
        Lambda Runtime
    dependency_manager: str, optional
        Dependency Manager for the Lambda Runtime Project
    output_dir: str, optional
        Output directory where project should be generated
        (the default is ".", which implies current folder)
    name: str
        Name of the project
    no_input : bool, optional
        Whether to prompt for input or to accept default values
        (the default is False, which prompts the user for values it doesn't know for baking)
    extra_context : Optional[Dict]
        An optional dictionary, the extra cookiecutter context

    Raises
    ------
    GenerateProjectFailedError
        If the process of baking a project fails
    """
    template = None

    if runtime and package_type == ZIP:
        for mapping in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values()))):
            if runtime in mapping["runtimes"] or any([r.startswith(runtime) for r in mapping["runtimes"]]):
                if not dependency_manager or dependency_manager == mapping["dependency_manager"]:
                    template = mapping["init_location"]
                    break

        if not template:
            msg = "Lambda Runtime {} does not support dependency manager: {}".format(runtime, dependency_manager)
            raise GenerateProjectFailedError(project=name, provider_error=msg)

    params = {"template": location if location else template, "output_dir": output_dir, "no_input": no_input}

    if extra_context:
        params["extra_context"] = extra_context

    LOG.debug("Parameters dict created with input given")
    LOG.debug("%s", params)

    if not location and name is not None:
        params["no_input"] = True
        LOG.debug("Parameters dict updated with project name as extra_context")
        LOG.debug("%s", params)

    try:
        LOG.debug("Baking a new template with cookiecutter with all parameters")
        cookiecutter(**params)
        # Fixes gradlew line ending issue caused by Windows git
        # gradlew is a shell script which should not have CR LF line endings
        # Putting the conversion after cookiecutter as cookiecutter processing will also change the line endings
        # https://github.com/cookiecutter/cookiecutter/pull/1407
        if platform.system().lower() == "windows":
            osutils.convert_files_to_unix_line_endings(output_dir, ["gradlew"])
    except RepositoryNotFound as e:
        # cookiecutter.json is not found in the template. Let's just clone it directly without using cookiecutter
        # and call it done.
        LOG.debug(
            "Unable to find cookiecutter.json in the project. Downloading it directly without treating "
            "it as a cookiecutter template"
        )
        project_output_dir = str(Path(output_dir, name)) if name else output_dir
        generate_non_cookiecutter_project(location=params["template"], output_dir=project_output_dir)

    except UnknownRepoType as e:
        raise InvalidLocationError(template=params["template"]) from e
    except CookiecutterException as e:
        raise GenerateProjectFailedError(project=name, provider_error=e) from e
