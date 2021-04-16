""" Represents AWS resource"""
from typing import List, Optional


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

    def __init__(self, arn: str) -> None:
        if not isinstance(arn, str):
            raise ValueError(f"Invalid ARN ({arn}) is not a String")

        parts = arn.split(":")
        try:
            self.partition: str = parts[1]
            self.service: str = parts[2]
            self.region: str = parts[3]
            self.account_id: str = parts[4]
            self.resource_id: str = parts[5]
            self.resource_type: Optional[str] = None
        except IndexError as ex:
            raise ValueError(f"Invalid ARN ({arn})") from ex

        if "/" in self.resource_id:
            resource_type_and_id: List[str] = self.resource_id.split("/")
            self.resource_type = resource_type_and_id[0]
            self.resource_id = resource_type_and_id[1]


class Resource:
    """
    Represents an AWS resource

    Attributes
    ----------
    arn: str
        the ARN of the resource
    is_user_provided: bool
        True if the user provided the ARN of the resource during the initialization. It indicates whether this pipeline-
        resource is provided by the user or created by SAM during `sam pipeline bootstrap`

    Methods
    -------
    name(self) -> Optional[str]:
        extracts and returns the resource name from its ARN
    """

    def __init__(self, arn: Optional[str]) -> None:
        self.arn: Optional[str] = arn
        self.is_user_provided: bool = bool(arn)

    def _get_arn_parts(self) -> Optional[ARNParts]:
        return ARNParts(self.arn) if self.arn else None

    def name(self) -> Optional[str]:
        """
        extracts and returns the resource name from its ARN
        Raises
        ------
        ValueError if the ARN is invalid
        """
        arn_parts: Optional[ARNParts] = self._get_arn_parts()
        return arn_parts.resource_id if arn_parts else None


class IamUser(Resource):
    """
    Represents an AWS IamUser resource
    Attributes
    ----------
    access_key_id: Optional[str]
        holds the AccessKeyId of the credential of this IAM user, if any.
    secret_access_key: Optional[str]
        holds the SecretAccessKey of the credential of this IAM user, if any.
    """

    def __init__(
        self, arn: Optional[str], access_key_id: Optional[str] = None, secret_access_key: Optional[str] = None
    ) -> None:
        self.access_key_id: Optional[str] = access_key_id
        self.secret_access_key: Optional[str] = secret_access_key
        super().__init__(arn=arn)


class S3Bucket(Resource):
    """
    Represents an AWS S3Bucket resource
    Attributes
    ----------
    kms_key_arn: Optional[str]
        The ARN of the KMS key used in encrypting this S3Bucket, if any.
    """

    def __init__(self, arn: Optional[str], kms_key_arn: Optional[str] = None) -> None:
        self.kms_key_arn: Optional[str] = kms_key_arn
        super().__init__(arn=arn)


class EcrRepo(Resource):
    """ Represents an AWS EcrRepo resource """

    def __init__(self, arn: Optional[str]) -> None:
        super().__init__(arn=arn)

    def get_uri(self) -> Optional[str]:
        """
        extracts and returns the URI of the given ECR repo from its ARN
        Raises
        ------
        ValueError if the ARN is invalid
        """
        arn_parts: Optional[ARNParts] = self._get_arn_parts()
        return (
            f"{arn_parts.account_id}.dkr.ecr.{arn_parts.region}.amazonaws.com/{arn_parts.resource_id}"
            if arn_parts
            else None
        )
