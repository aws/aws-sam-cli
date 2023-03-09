import logging
import os
import webbrowser
from enum import Enum
from typing import Optional

LOG = logging.getLogger(__name__)


class OpenMode(Enum):
    SameWindow = 0
    NewWindow = 1
    NewTab = 2


class BrowserConfiguration:
    def __init__(self, browser_name: Optional[str] = None, open_mode: Optional[OpenMode] = None):
        self.open_mode = open_mode
        self.web_browser = webbrowser.get(browser_name)

    def launch(self, url):
        open_mode = self.open_mode.value if self.open_mode else OpenMode.SameWindow.value
        try:
            self.web_browser.open(url=url, new=open_mode)
        except webbrowser.Error as ex:
            LOG.info(f"Error occurred when attempting to open a web browser:{os.linesep}{str(ex)}")
