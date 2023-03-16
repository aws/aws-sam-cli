"""
Library housing the logic for handling AWS SAM CLI documentation pages
"""
import json
import logging
from pathlib import Path

from samcli.lib.docs.browser_configuration import BrowserConfiguration

LOG = logging.getLogger(__name__)

DOCS_CONFIG_FILE = "documentation_links.json"
LANDING_PAGE = "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html"


class Documentation:
    def __init__(self, browser: BrowserConfiguration, command: str):
        self.browser = browser
        self.command = command

    @property
    def url(self):
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

    def get_docs_link_for_command(self):
        return Documentation.load().get(self.command, LANDING_PAGE)

    @staticmethod
    def load() -> dict:
        with open(Path(__file__).parent / DOCS_CONFIG_FILE) as f:
            return json.load(f)
