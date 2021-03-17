"""
Plugins are sub-sets of templates, it encapsulate common behavior of different templates and plugged to each of them
"""
from typing import NamedTuple
from .processor import Processor
from .interactive_flow import InteractiveFlow


class Plugin(NamedTuple):
    """
    A plugin is a sub cookiecutter template. it has its own interactive_flow to prompt the user for answers to
    its own context and it also has its preprocessor and postprocessor.  plugin's components are appended to the
    templates corresponding component; interactive_flows, preprocessors and postprocessors.
    plugins encapsulate common logic of different templates in one place to be passed(plugged) to each template.

    Attributes
    ----------
    interactive_flow: InteractiveFlow
        a flow of questions to be appended to the series of interactive_flows of the parent template.
    preprocessor: Processor
        a processor to be appended to the series of processors of the parent template.
    postprocessor: Processor
        a processor to be appended to the series of postprocessors of the parent template.
    """

    interactive_flow: InteractiveFlow
    preprocessor: Processor
    postprocessor: Processor
