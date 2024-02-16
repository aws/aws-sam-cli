"""
Library housing the logic for handling AWS SAM CLI documentation pages
"""

import json
import logging
from pathlib import Path
from typing import Dict

from samcli.lib.docs.browser_configuration import BrowserConfiguration

LOG = logging.getLogger(__name__)

DOCS_CONFIG_FILE = "documentation_links.json"
LANDING_PAGE = "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html"


class Documentation:
    def __init__(self, browser: BrowserConfiguration, command: str):
        """
        Constructor for instantiating a Documentation object
        Parameters
        ----------
        browser: BrowserConfiguration
            Configuration for a browser object used to launch docs pages
        command: str
            String name of the command for which to find documentation
        """
        self.browser = browser
        self.command = command

    @property
    def url(self) -> str:
        """
        Returns the url to be opened
        """
        return self.get_docs_link_for_command()

    def open_docs(self):
        """
        Open the documentation page in a configured web browser

        Raises
        ------
        BrowserConfigurationError
        """
        LOG.debug(f"Launching {self.url} in a browser.")
        self.browser.launch(self.url)

    def get_docs_link_for_command(self) -> str:
        """
        Get the documentation URL from a specific command

        Returns
        -------
        str
            String representing the link to be opened
        """
        return Documentation.load().get(self.command, LANDING_PAGE)

    @staticmethod
    def load() -> Dict[str, str]:
        """
        Opens the configuration file and returns the contents

        Returns
        -------
        Dict[str, Any]
            A dictionary containing commands and their corresponding docs URLs
        """
        with open(Path(__file__).parent / DOCS_CONFIG_FILE) as f:
            return dict(json.load(f))
