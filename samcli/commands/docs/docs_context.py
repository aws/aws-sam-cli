from click import echo

from samcli.lib.docs.browser_configuration import BrowserConfiguration
from samcli.lib.docs.documentation import Documentation


class DocsContext:
    URL = "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html"

    def __init__(self, config_file: str, config_env: str):
        self.config_file = config_file
        self.config_env = config_env

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):
        echo(f"Opening documentation in the browser. If the page fails to open, use the following link: {self.URL}")
        browser = BrowserConfiguration()
        documentation = Documentation(browser=browser, url=self.URL)
        documentation.open_docs()
