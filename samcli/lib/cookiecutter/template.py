"""
This is the core module of the cookiecutter workflow, it defines how to create a template, prompt the user for
values of the context and how to generate a project from the given template and provided context
"""
import logging
from typing import Dict, List, Optional

from cookiecutter.exceptions import RepositoryNotFound, UnknownRepoType
from cookiecutter.main import cookiecutter

from samcli.commands.exceptions import UserException
from samcli.lib.init.arbitrary_project import generate_non_cookiecutter_project
from .exceptions import GenerateProjectFailedError, InvalidLocationError, PreprocessingError, PostprocessingError
from .interactive_flow import InteractiveFlow
from .plugin import Plugin
from .processor import Processor

LOG = logging.getLogger(__name__)


class Template:
    """
    A class for project generation based on cookiecutter template

    Attributes
    ----------
    location: str
        Template location (git, mercurial, http(s), path)
    interactive_flows: Optional[List[InteractiveFlow]]
        An optional series of interactive questions to be asked to the user where the answers are used to fulfill
        the values of the cookiecutter.json keys, i.e. the cookiecutter context
    preprocessors: Optional[List[Processor]]
        An optional series of processes to be executed before generating the cookiecutter project. These processes
        are usually used to manipulate the cookiecutter context or doing some bootstrapping before generating
        the cookiecutter project.
        preprocessors are different than cookiecutter's hooks in the sense that they can mutate the context while
        the pre_gen_project hooks can't.
    postprocessors: Optional[List[Processor]]
        An optional series of processes to be executed after generating the cookiecutter project. These processes
        are usually used to clean up resources and to print messages to the user after successfully generating
        the cookiecutter project.
    plugins: Optional[List[Plugin]]
        An optional series of plugins to be plugged in. A plugin defines its own interactive_flow, preprocessor
        and postprocessor. A plugin is a sub-set of the template, if there is a common behavior among multiple
        templates, it is better to be extracted to a plugin that can then be plugged in to each of these templates.
    metadata: Optional[Dict]
        An optional dictionary with extra information about the template

    Methods
    -------
    run_interactive_flows() -> Dict:
        runs the interactive_flows(questions) one be one then combines and returns the answers in one dictionary
        in the form of {question.key: answer}
    generate_project(context) -> None:
        runs the preprocessors chain passing in the given context to the first processor which process it then produce
        a new context which is passed to the next preprocessor and so on.
        After that, it execute the cookiecutter generator to generate the project with the final preprocessed context.
        Finally, it runs the postprocessors chain with the same manner like the preprocessors.
    """

    def __init__(
        self,
        location: str,
        interactive_flows: Optional[List[InteractiveFlow]] = None,
        preprocessors: Optional[List[Processor]] = None,
        postprocessors: Optional[List[Processor]] = None,
        plugins: Optional[List[Plugin]] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Initialize the class

        Parameters
        ----------
        location: str
            Template location (git, mercurial, http(s), path)
        interactive_flows: Optional[List[InteractiveFlow]]
            An optional series of interactive questions to be asked to the user where the answers are used to fulfill
            the values of the cookiecutter.json keys, i.e. the cookiecutter context
        preprocessors: Optional[List[Processor]]
            An optional series of processes to be executed before generating the cookiecutter project. These processes
            are usually used to manipulate the cookiecutter context or doing some bootstrapping before generating
            the cookiecutter project.
        postprocessors: Optional[List[Processor]]
            An optional series of processes to be executed after generating the cookiecutter project. These processes
            are usually used to clean up resources and to print messages to the user after successfully generating
            the cookiecutter project.
        plugins: Optional[List[Plugin]]
            An optional series of plugins to be plugged in. A plugin defines its own interactive_flow, preprocessor
            and postprocessor. A plugin is a sub-set of the template, if there is a common behavior among multiple
            templates, it is better to be extracted to a plugin that can then be plugged in to each of these templates.
        metadata: Optional[Dict]
            An optional dictionary with extra information about the template
        """
        self._location = location
        self._interactive_flows = interactive_flows or []
        self._preprocessors = preprocessors or []
        self._postprocessors = postprocessors or []
        self._plugins = plugins or []
        for plugin in self._plugins:
            if plugin.interactive_flow:
                self._interactive_flows.append(plugin.interactive_flow)
            if plugin.preprocessor:
                self._preprocessors.append(plugin.preprocessor)
            if plugin.postprocessor:
                self._postprocessors.append(plugin.postprocessor)
        self.metadata = metadata

    def run_interactive_flows(self, context: Optional[Dict] = None) -> Dict:
        """
        prompt the user a series of questions' flows and gather the answers to create the cookiecutter context.
        The questions are identified by keys. If multiple questions, whether within the same flow or across
        different flows, have the same key, the last question will override the others and we will get only the
        answer of this question.

        Raises:
            UserException(ClickException) if anything went wrong.

        Returns:
            A Dictionary in the form of {question.key: answer} representing user's answers to the flows' questions
        """
        try:
            context = context if context else {}
            for flow in self._interactive_flows:
                context = flow.run(context)
            return context
        except Exception as e:
            raise UserException(str(e), wrapped_from=e.__class__.__name__) from e

    def generate_project(self, context: Dict, output_dir: str) -> None:
        """
        Generates a project based on this cookiecutter template and the given context. The context is first
        processed and manipulated by series of preprocessors(if any) then the project is generated and finally
        the series of postprocessors(if any) are executed.

        Parameters
        ----------
        context: Dict
            the cookiecutter context to fulfill the values of cookiecutter.json keys
        output_dir: str
            the directory where project will be generated in

        Raises
        ------
        PreprocessingError
            xxx
        InvalidLocationError
            if the given location is not from a known repo type
        GenerateProjectFailedError
            if something else went wrong
        PostprocessingError
            yyy
        """
        try:
            LOG.debug("preprocessing the cookiecutter context")
            for processor in self._preprocessors:
                context = processor.run(context)
        except Exception as e:
            raise PreprocessingError(template=self._location, provider_error=e) from e

        try:
            LOG.debug("Baking a new template with cookiecutter with all parameters")
            cookiecutter(
                template=self._location,
                output_dir=output_dir,
                no_input=True,
                extra_context=context,
                overwrite_if_exists=True,
            )
        except RepositoryNotFound:
            # cookiecutter.json is not found in the template. Let's just clone it directly without
            # using cookiecutter and call it done.
            LOG.debug(
                "Unable to find cookiecutter.json in the project. Downloading it directly without treating "
                "it as a cookiecutter template"
            )
            generate_non_cookiecutter_project(location=self._location, output_dir=".")
        except UnknownRepoType as e:
            raise InvalidLocationError(template=self._location) from e
        except Exception as e:
            raise GenerateProjectFailedError(template=self._location, provider_error=e) from e

        try:
            LOG.debug("postprocessing the cookiecutter context")
            for processor in self._postprocessors:
                context = processor.run(context)
        except Exception as e:
            raise PostprocessingError(template=self._location, provider_error=e) from e
