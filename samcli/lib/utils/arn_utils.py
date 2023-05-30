"""
Module for utilities for ARN (Amazon Resource Names)
"""


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
    resource_id: str

    def __init__(self, arn: str) -> None:
        parts = arn.split(":")
        try:
            [_, self.partition, self.service, self.region, self.account_id, self.resource_id] = parts
        except ValueError as ex:
            raise InvalidArnValue(f"Invalid ARN ({arn})") from ex
