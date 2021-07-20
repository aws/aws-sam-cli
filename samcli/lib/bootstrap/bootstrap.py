"""
Bootstrap's user's development environment by creating cloud resources required by SAM CLI
"""

import json
import logging
from samcli import __version__
from samcli.cli.global_config import GlobalConfig
from samcli.commands.exceptions import UserException
from samcli.lib.utils.managed_cloudformation_stack import manage_stack as manage_cloudformation_stack

SAM_CLI_STACK_NAME = "aws-sam-cli-managed-default"
LOG = logging.getLogger(__name__)


def manage_stack(profile, region):
    outputs = manage_cloudformation_stack(
        profile=None, region=region, stack_name=SAM_CLI_STACK_NAME, template_body=_get_stack_template()
    )

    try:
        bucket_name = next(o for o in outputs if o["OutputKey"] == "SourceBucket")["OutputValue"]
    except StopIteration as ex:
        msg = (
            "Stack " + SAM_CLI_STACK_NAME + " exists, but is missing the managed source bucket key. "
            "Failing as this stack was likely not created by the AWS SAM CLI."
        )
        raise UserException(msg) from ex
    # This bucket name is what we would write to a config file
    return bucket_name


def _get_stack_template():
    gc = GlobalConfig()
    info = {"version": __version__, "installationId": gc.installation_id if gc.installation_id else "unknown"}

    template = """
    AWSTemplateFormatVersion : '2010-09-09'
    Transform: AWS::Serverless-2016-10-31
    Description: Managed Stack for AWS SAM CLI

    Metadata:
        SamCliInfo: {info}

    Resources:
      SamCliSourceBucket:
        Type: AWS::S3::Bucket
        Properties:
          VersioningConfiguration:
            Status: Enabled
          Tags:
            - Key: ManagedStackSource
              Value: AwsSamCli

      SamCliSourceBucketBucketPolicy:
        Type: AWS::S3::BucketPolicy
        Properties:
          Bucket: !Ref SamCliSourceBucket
          PolicyDocument:
            Statement:
              -
                Action:
                  - "s3:GetObject"
                Effect: "Allow"
                Resource:
                  Fn::Join:
                    - ""
                    -
                      - "arn:"
                      - !Ref AWS::Partition
                      - ":s3:::"
                      - !Ref SamCliSourceBucket
                      - "/*"
                Principal:
                  Service: serverlessrepo.amazonaws.com
                Condition:
                  StringEquals:
                    aws:SourceAccount: !Ref AWS::AccountId

    Outputs:
      SourceBucket:
        Value: !Ref SamCliSourceBucket
    """

    return template.format(info=json.dumps(info))
