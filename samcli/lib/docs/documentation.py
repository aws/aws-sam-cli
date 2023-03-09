import logging

from samcli.lib.docs.browser_configuration import BrowserConfiguration

LOG = logging.getLogger(__name__)


class Documentation:
    def __init__(self, browser: BrowserConfiguration, url: str):
        self.browser = browser
        self.url = url

    def open_docs(self):
        LOG.debug(f"Launching {self.url} in a browser.")
        self.browser.launch(self.url)
