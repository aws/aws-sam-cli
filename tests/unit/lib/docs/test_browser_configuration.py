from unittest import TestCase

import webbrowser
from unittest.mock import Mock

from samcli.lib.docs.browser_configuration import BrowserConfiguration, OpenMode


class TestBrowserConfiguration(TestCase):
    def setUp(self):
        self.url = "https://sam-is-the-best.com"

    def test_launch_default_browser_configuration(self):
        webbrowser_mock = Mock()
        browser = BrowserConfiguration()
        browser.web_browser = webbrowser_mock
        browser.launch(url=self.url)
        browser.web_browser.open.assert_called_once_with(url=self.url, new=0)

    def test_launch_browser_with_open_mode(self):
        webbrowser_mock = Mock()
        browser = BrowserConfiguration(open_mode=OpenMode.NewTab)
        browser.web_browser = webbrowser_mock
        browser.launch(url=self.url)
        browser.web_browser.open.assert_called_once_with(url=self.url, new=2)

    def test_launch_default_browser_fails(self):
        webbrowser_mock = Mock()
        webbrowser_mock.open.side_effect = webbrowser.Error
        browser = BrowserConfiguration()
        browser.web_browser = webbrowser_mock
        with self.assertLogs(level="INFO") as log:
            browser.launch(self.url)
            self.assertIn("Error occurred when attempting to open a web browser", log.output[0])
