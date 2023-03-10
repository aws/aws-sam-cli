"""
Context class for handling `sam docs` command logic
"""
from click import echo

from samcli.lib.docs.browser_configuration import BrowserConfiguration, BrowserConfigurationError
from samcli.lib.docs.documentation import Documentation

SUCCESS_MESSAGE = "Documentation page opened in a browser"
ERROR_MESSAGE = "Failed to open a web browser. Use the following link to navigate to the documentation page: {URL}"


class DocsContext:
    URL = "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):
        """
        Run the necessary logic for the `sam docs` command
        """
        browser = BrowserConfiguration()
        documentation = Documentation(browser=browser, url=self.URL)
        try:
            documentation.open_docs()
        except BrowserConfigurationError:
            echo(ERROR_MESSAGE.format(URL=self.URL))
        else:
            echo(SUCCESS_MESSAGE)
