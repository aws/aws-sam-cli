"""
Library housing the logic for handling AWS SAM CLI documentation pages
"""
import logging

from samcli.lib.docs.browser_configuration import BrowserConfiguration

LOG = logging.getLogger(__name__)


class Documentation:
    def __init__(self, browser: BrowserConfiguration, url: str):
        self.browser = browser
        self.url = url

    def open_docs(self):
        """
        Open the documentation page in a configured web browser

        Raises
        ------
        BrowserConfigurationError
        """
        LOG.debug(f"Launching {self.url} in a browser.")
        self.browser.launch(self.url)
