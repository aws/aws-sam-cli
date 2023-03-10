import os
from unittest import TestCase

import webbrowser
from unittest.mock import Mock, patch

from samcli.lib.docs.browser_configuration import BrowserConfiguration, OpenMode, BrowserConfigurationError


class TestBrowserConfiguration(TestCase):
    def setUp(self):
        self.url = "https://sam-is-the-best.com"

    @patch("samcli.lib.docs.browser_configuration.webbrowser.get")
    def test_launch_default_browser_configuration(self, browser_mock_get):
        webbrowser_mock = Mock()
        browser_mock_get.return_value = webbrowser_mock
        browser = BrowserConfiguration()
        browser.web_browser = webbrowser_mock
        browser.launch(url=self.url)
        browser.web_browser.open.assert_called_once_with(url=self.url, new=0)

    @patch("samcli.lib.docs.browser_configuration.webbrowser.get")
    def test_launch_browser_with_open_mode(self, browser_mock_get):
        webbrowser_mock = Mock()
        browser_mock_get.return_value = webbrowser_mock
        browser = BrowserConfiguration(open_mode=OpenMode.NewTab)
        browser.web_browser = webbrowser_mock
        browser.launch(url=self.url)
        browser.web_browser.open.assert_called_once_with(url=self.url, new=2)

    @patch("samcli.lib.docs.browser_configuration.webbrowser.get")
    def test_launch_default_browser_fails(self, browser_mock_get):
        browser_exception = webbrowser.Error("Something went wrong")
        webbrowser_mock = webbrowser.BaseBrowser()
        webbrowser_mock.open = Mock()
        webbrowser_mock.open.side_effect = browser_exception
        browser_mock_get.return_value = webbrowser_mock
        browser = BrowserConfiguration()
        with self.assertRaises(BrowserConfigurationError) as ex:
            browser.launch(self.url)
        self.assertEqual("Error occurred when attempting to open a web browser", ex.exception.args[0])
