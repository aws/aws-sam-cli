"""
Module for utilities for ARN (Amazon Resource Names)
"""

import re


class InvalidArnValue(ValueError):
    pass


class ARNParts:
    """
    Decompose a given ARN into its parts https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html

    Attributes
    ----------
    partition: str
        the partition part(AWS, aws-cn or aws-us-gov)  of the ARN
    service: str
        the service part(S3, IAM, ECR, ...etc) of the ARN
    region: str
        the AWS region part(us-east-1, eu-west-1, ...etc) of the ARN
    account-id: str
        the account-id part of the ARN
    resource-id: str
        the resource-id part of the ARN
    resource-type: str
        the resource-type part of the ARN
    """

    partition: str
    service: str
    region: str
    account_id: str
    resource_type: str
    resource_id: str

    def __init__(self, arn: str) -> None:
        # Regex pattern formed based on the 3 ARN general formats found here:
        # https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html
        arn_pattern = (
            r"arn:([a-zA-Z0-9_-]+):"  # Pattern for partition
            r"([a-zA-Z0-9_-]+):"  # Pattern for service
            r"([a-zA-Z0-9_-]*):"  # Pattern for region
            r"([a-zA-Z0-9_-]*)"  # Pattern for account_id
            r"(?::([a-zA-Z0-9_-]+))?"  # Pattern for resource_type if it exists
            r"(?::(.+))"  # Pattern for resource_id if it exists
        )

        matched_arn = re.match(arn_pattern, arn)
        if not matched_arn:
            raise InvalidArnValue(f"Invalid ARN ({arn}) provided")

        self.partition = matched_arn.group(1)
        self.service = matched_arn.group(2)
        self.region = matched_arn.group(3) if matched_arn.group(3) else ""
        self.account_id = matched_arn.group(4) if matched_arn.group(4) else ""
        self.resource_type = matched_arn.group(5) if matched_arn.group(5) else ""
        if matched_arn.group(5):
            # This handles the Arns of services with the format:
            # arn:partition:service:region:account-id:resource-type:resource-id
            self.resource_type = matched_arn.group(5)
            self.resource_id = matched_arn.group(6) if matched_arn.group(6) else ""
        elif "/" in matched_arn.group(6):
            # This handles the Arns of services with the format:
            # arn:partition:service:region:account-id:resource-type/resource-id
            split_resource_type_and_id = matched_arn.group(6).split("/", 1)
            self.resource_type = split_resource_type_and_id[0]
            self.resource_id = split_resource_type_and_id[1]
        else:
            # This handles the Arns of services with the format:
            # arn:partition:service:region:account-id:resource-id
            self.resource_type = ""
            self.resource_id = matched_arn.group(6) if matched_arn.group(6) else ""
