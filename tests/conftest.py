import os


if "__SAM_CLI_TELEMETRY_ENDPOINT_URL" not in os.environ:
    os.environ["__SAM_CLI_TELEMETRY_ENDPOINT_URL"] = ""
