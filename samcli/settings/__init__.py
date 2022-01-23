"""
Default Settings used by the CLI.

We will checkin the development.py file into source control. So by default only the dev configs
will be available. When preparing the CLI for production release, the release process will inject
production.py file into this folder and remove development.py. When customers install SAM CLI from
PyPi or any other official installation mechanism, they will get the production settings.

Ensure the configuration variables defined in production.py and development.py have exact same names.


Following variables are exported by this module:

    ``telemetry_endpoint_url``: string URL where Telemetry data should be published to

"""

import os


telemetry_endpoint_url = os.getenv(
    "__SAM_CLI_TELEMETRY_ENDPOINT_URL", "https://aws-serverless-tools-telemetry.us-west-2.amazonaws.com/metrics"
)
