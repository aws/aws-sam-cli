"""
Base class for SAM Template providers
"""

from samcli.lib.samlib.wrapper import SamTranslatorWrapper


class SamBaseProvider(object):
    """
    Base class for SAM Template providers
    """

    @staticmethod
    def get_template(template_dict):
        template_dict = template_dict or {}
        if template_dict:
            template_dict = SamTranslatorWrapper(template_dict).run_plugins()

        return template_dict
