import os
import time
import shutil
import tempfile
from unittest import TestCase

from boto3.session import Session
from botocore.exceptions import ClientError
from click.testing import CliRunner
from samcli.commands.init import cli as init_cmd

AWS_CONFIG_FILE = "AWS_CONFIG_FILE"
AWS_SHARED_CREDENTIALS_FILE = "AWS_SHARED_CREDENTIALS_FILE"
DEFAULT = "default"
AWS_DEFAULT_REGION = "AWS_DEFAULT_REGION"
AWS_PROFILE = "AWS_PROFILE"
SLEEP_TIME = 1


class SchemaTestDataSetup(TestCase):
    original_cred_file = None
    original_config_file = None
    original_profile = None
    original_region = None

    @classmethod
    def setUpClass(cls):
        session = Session()
        schemas_client = session.client("schemas", region_name=session.region_name)
        # all setup is done here to avoid creating side effects in test. Currently we are using CLI and
        # the input is number which is only valid when everything is in place.
        setup_partner_schema_data("partner-registry", schemas_client)
        setup_schema_data_for_pagination("test-pagination", schemas_client)
        setup_non_partner_schema_data("other-schema", schemas_client)
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Hello World Example
        # N: do not use DEFAULT hello world template
        # 11: Java runtime
        # 2: dependency manager maven
        # eb-app-maven: response to name
        # Y: clone/update the source repo
        # 1: hello world

        user_input = """
1
1
N
5
1
2
eb-app-maven
    """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

    def _init_custom_config(self, profile, region):
        self.config_dir = tempfile.mkdtemp()
        env = os.environ
        if AWS_CONFIG_FILE in env:
            self.original_config_file = env[AWS_CONFIG_FILE]
        if AWS_SHARED_CREDENTIALS_FILE in env:
            self.original_cred_file = env[AWS_SHARED_CREDENTIALS_FILE]
        if AWS_PROFILE in env:
            self.original_profile = env[AWS_PROFILE]
        if AWS_DEFAULT_REGION in env:
            self.original_region = env[AWS_DEFAULT_REGION]

        custom_config = self._create_config_file(profile, region)
        session = Session()
        custom_cred = self._create_cred_file(
            profile,
            session.get_credentials().access_key,
            session.get_credentials().secret_key,
            session.get_credentials().token,
        )

        env[AWS_CONFIG_FILE] = custom_config
        env[AWS_SHARED_CREDENTIALS_FILE] = custom_cred
        env[AWS_PROFILE] = profile
        env[AWS_DEFAULT_REGION] = region

    def _tear_down_custom_config(self):
        env = os.environ

        if self.original_config_file is None:
            del env[AWS_CONFIG_FILE]
        else:
            env[AWS_CONFIG_FILE] = self.original_config_file

        if self.original_cred_file is None:
            del env[AWS_SHARED_CREDENTIALS_FILE]
        else:
            env[AWS_SHARED_CREDENTIALS_FILE] = self.original_cred_file

        if self.original_profile is None:
            del env[AWS_PROFILE]
        else:
            env[AWS_PROFILE] = self.original_profile

        if self.original_region is None:
            del env[AWS_DEFAULT_REGION]
        else:
            env[AWS_DEFAULT_REGION] = self.original_region

        shutil.rmtree(self.config_dir, ignore_errors=True)

    def _create_config_file(self, profile, region):
        if profile == DEFAULT:
            config_file_content = "[{0}]\noutput = json\nregion = {1}".format(profile, region)
        else:
            config_file_content = "[profile {0}]\noutput = json\nregion = {1}".format(profile, region)

        custom_config = os.path.join(self.config_dir, "customconfig")
        print("Writing custom config to {}".format(custom_config))
        with open(custom_config, "w") as file:
            file.write(config_file_content)
        return custom_config

    def _create_cred_file(self, profile, access_key, secret_key, session_token=None):
        cred_file_content = self._create_cred_profile("default", access_key, secret_key, session_token)
        if profile != DEFAULT:
            cred_file_content += f"\n{self._create_cred_profile(profile, access_key, secret_key, session_token)}"
        custom_cred = os.path.join(self.config_dir, "customcred")
        print("Writing custom creds to {}".format(custom_cred))
        with open(custom_cred, "w") as file:
            file.write(cred_file_content)
        return custom_cred

    def _create_cred_profile(self, profile_name, access_key, secret_key, session_token=None):
        """
        Method to create aws credentials entry similar to ~/.aws/credentials file format.
        """
        cred_profile_content = f"""
[{profile_name}]
aws_access_key_id = {access_key}
aws_secret_access_key = {secret_key}
"""
        if session_token:
            cred_profile_content += f"aws_session_token={session_token}\n"
        return cred_profile_content


def setup_partner_schema_data(registry_name, schemas_client):
    _create_registry_if_not_exist(registry_name, schemas_client)
    _create_3p_schemas(registry_name, schemas_client, 2)


def setup_schema_data_for_pagination(registry_name, schemas_client):
    _create_registry_if_not_exist(registry_name, schemas_client)
    _create_3p_schemas(registry_name, schemas_client, 12)


def setup_non_partner_schema_data(registry_name, schemas_client):
    _create_registry_if_not_exist(registry_name, schemas_client)
    _create_2p_schemas(registry_name, schemas_client)


def _create_registry_if_not_exist(registry_name, schemas_client):
    try:
        schemas_client.describe_registry(RegistryName=registry_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            schemas_client.create_registry(RegistryName=registry_name, Description=registry_name)
            time.sleep(SLEEP_TIME)


def _create_3p_schemas(registry_name, schemas_client, no_of_schemas):
    content = (
        '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"TicketCreated"},"paths":{},"components":{"schemas":{"AWSEvent":{"type":"object",'
        '"required":["detail-type","resources","id","source","time","detail","region","version","account"],"x-amazon-events-detail-type":"MongoDB Trigger for '
        'my_store.reviews","x-amazon-events-source":"aws.partner-mongodb.com","properties":{"detail":{'
        r'"$ref":"#\/components\/schemas\/aws.partner\/mongodb.com\/Ticket.Created"},"detail-type":{"type":"string"},"resources":{"type":"array",'
        '"items":{"type":"string"}},"id":{"type":"string"},"source":{"type":"string"},"time":{"type":"string","format":"date-time"},'
        '"region":{"type":"string","enum":["ap-south-1","eu-west-3","eu-north-1","eu-west-2","eu-west-1","ap-northeast-2","ap-northeast-1","me-south-1",'
        '"sa-east-1","ca-central-1","ap-east-1","cn-north-1","us-gov-west-1","ap-southeast-1","ap-southeast-2","eu-central-1","us-east-1","us-west-1",'
        '"cn-northwest-1","us-west-2"]},"version":{"type":"string"},"account":{"type":"string"}}},"TicketCreated":{"type":"object","required":["creator",'
        '"department","ticketId"],"properties":{"creator":{"type":"string"},"department":{"type":"string"},"ticketId":{"type":"string"}}}}}} '
    )
    for i in range(0, no_of_schemas):
        schema_name = "schema_test-%s" % i
        _create_schema_if_not_exist(registry_name, schema_name, content, "1", "test-schema", "OpenApi3", schemas_client)


def _create_2p_schemas(registry_name, schemas_client):
    content = (
        '{"openapi":"3.0.0","info":{"version":"1.0.0","title":"SomeAwesomeSchema"},"paths":{},"components":{"schemas":{"Some Awesome Schema":{"type":"object",'
        '"required":["foo","bar","baz"],"properties":{"foo":{"type":"string"},"bar":{"type":"string"},"baz":{"type":"string"}}}}}} '
    )
    for i in range(0, 2):
        schema_name = "schema_test-%s" % i
        _create_schema_if_not_exist(registry_name, schema_name, content, "1", "test-schema", "OpenApi3", schemas_client)


def _create_schema_if_not_exist(
    registry_name, schema_name, content, schema_version, schema_description, schema_type, schemas_client
):
    try:
        schemas_client.describe_schema(RegistryName=registry_name, SchemaName=schema_name, SchemaVersion=schema_version)
    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            schemas_client.create_schema(
                RegistryName=registry_name,
                SchemaName=schema_name,
                Content=content,
                Description=schema_description,
                Type=schema_type,
            )
            time.sleep(SLEEP_TIME)
