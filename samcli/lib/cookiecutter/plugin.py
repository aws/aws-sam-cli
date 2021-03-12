"""
Plugins are sub-sest of templates, it encapsulate common behavior of different templates and plugged to each of them
"""
from .processor import Processor
from .interactive_flow import InteractiveFlow


class Plugin:
    """
    A plugin is a sub cookiecutter template. it has its own interactive_flow to prompt the user for answers to
    its own context and it also has its preprocessor and postprocessor.  plugin's components are appended to the
    templates corresponding component; interactive_flows, preprocessors and postprocessors.
    plugins encapsulate common logic of different templates in one place to be passed(plugged) to each template.

    Attributes
    ----------
    _interactive_flow: InteractiveFlow
        a flow of questions to be appended to the series of interactive_flows of the parent template.
    _preprocessor: Processor
        a processor to be appended to the series of processors of the parent template.
    _postprocessor: Processor
        a processor to be appended to the series of postprocessors of the parent template.
    """

    def __init__(self, interactive_flow: InteractiveFlow, preprocessor: Processor, postprocessor: Processor):
        self._interactive_flow = interactive_flow
        self._preprocessor = preprocessor
        self._postprocessor = postprocessor

    @property
    def interactive_flow(self):
        return self._interactive_flow

    @property
    def preprocessor(self):
        return self._preprocessor

    @property
    def postprocessor(self):
        return self._postprocessor
