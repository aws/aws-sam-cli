import uuid
from collections import namedtuple

import boto3

from tests.integration.local.invoke.invoke_integ_base import InvokeIntegBase
from pathlib import Path


class LayerUtils(object):
    def __init__(self, region):
        self.region = region
        self.layer_meta = namedtuple("LayerMeta", ["layer_name", "layer_arn", "layer_version"])
        self.lambda_client = boto3.client("lambda", region_name=region)
        self.parameters_overrides = {}
        self.layers_meta = []
        self.layer_zip_parent = InvokeIntegBase.get_integ_dir().joinpath("testdata", "invoke", "layer_zips")

    @staticmethod
    def generate_layer_name():
        return str(uuid.uuid4()).replace("-", "")[:10]

    def upsert_layer(self, layer_name, ref_layer_name, layer_zip):
        with open(str(Path.joinpath(self.layer_zip_parent, layer_zip)), "rb") as zip_contents:
            resp = self.lambda_client.publish_layer_version(
                LayerName=layer_name, Content={"ZipFile": zip_contents.read()}
            )
            self.parameters_overrides[ref_layer_name] = resp["LayerVersionArn"]
            self.layers_meta.append(
                self.layer_meta(layer_name=layer_name, layer_arn=resp["LayerArn"], layer_version=resp["Version"])
            )

    def delete_layers(self):
        for layer_meta in self.layers_meta:
            self.lambda_client.delete_layer_version(
                LayerName=layer_meta.layer_arn, VersionNumber=layer_meta.layer_version
            )
