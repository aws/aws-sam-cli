"""
Library housing logic for handling web browsers
"""

import logging
import webbrowser
from enum import Enum
from typing import Optional

LOG = logging.getLogger(__name__)


class OpenMode(Enum):
    SameWindow = 0
    NewWindow = 1
    NewTab = 2


class BrowserConfigurationError(Exception):
    pass


class BrowserConfiguration:
    def __init__(self, browser_name: Optional[str] = None, open_mode: Optional[OpenMode] = None):
        self.open_mode = open_mode
        self.browser_name = browser_name

    def launch(self, url: str):
        """
        Launch a browser session (or open an existing tab by default) for a given URL

        Parameters
        ----------
        url: str
            The URL string to open in the browser

        Raises
        ------
        BrowserConfigurationError

        """

        open_mode = self.open_mode.value if self.open_mode else OpenMode.SameWindow.value
        try:
            web_browser: webbrowser.BaseBrowser = webbrowser.get(self.browser_name)
            web_browser.open(url=url, new=open_mode)
        except webbrowser.Error as ex:
            raise BrowserConfigurationError("Error occurred when attempting to open a web browser") from ex
