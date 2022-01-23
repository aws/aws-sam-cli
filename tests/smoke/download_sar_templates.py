import requests
import os
import logging
import time
import boto3


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger()
TEMPLATE_FOLDER = os.path.join("templates", "sar")


def download(count=100):

    sar_browse_url = "https://shr32taah3.execute-api.us-east-1.amazonaws.com/Prod/applications/browse"
    current_page = 1
    retry_count = 0
    apps = []

    while len(apps) < count and retry_count < 10:
        try:
            response = requests.get(
                sar_browse_url,
                {
                    "pageSize": count if count < 10 else 10,
                    "pageNumber": current_page,
                    "includeAppsWithCapabilities": "CAPABILITY_IAM,CAPABILITY_NAMED_IAM,CAPABILITY_RESOURCE_POLICY,CAPABILITY_AUTO_EXPAND",
                },
            )

            response.raise_for_status()
            result = response.json()

            # Successful request
            apps = apps + result["applications"]
            current_page += 1
            retry_count = 0
        except requests.exceptions.RequestException as ex:
            LOG.warning("Got throttled by SAR", exc_info=ex)
            retry_count += 1

    for index, app in enumerate(apps):
        app_id = app["id"]
        name = app["name"]
        template_file_name = os.path.join(TEMPLATE_FOLDER, name + "-template.yaml")
        LOG.info("[%s/%s] %s", index, count, name)
        _download_templates(app_id, template_file_name)
        time.sleep(0.1)  # 100ms aka 10 TPS


def _download_templates(app_id, template_file_path):
    sar = boto3.client("serverlessrepo")
    response = sar.get_application(ApplicationId=app_id)

    template_url = response["Version"]["TemplateUrl"]

    with open(template_file_path, "wb") as fp:
        r = requests.get(template_url, stream=True)
        for chunk in r.iter_content(chunk_size=128):
            fp.write(chunk)


if __name__ == "__main__":
    count = 100
    LOG.info("Downloading %s templates", count)
    download(count=count)
