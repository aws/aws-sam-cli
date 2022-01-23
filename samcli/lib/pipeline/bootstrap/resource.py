""" Represents AWS resource"""
from typing import Optional


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
            raise ValueError(f"Invalid ARN ({arn})") from ex


class Resource:
    """
    Represents an AWS resource

    Attributes
    ----------
    arn: str
        the ARN of the resource
    comment: str
        the comment of the resource
    is_user_provided: bool
        True if the user provided the ARN of the resource during the initialization. It indicates whether this pipeline-
        resource is provided by the user or created by SAM during `sam pipeline bootstrap`

    Methods
    -------
    name(self) -> Optional[str]:
        extracts and returns the resource name from its ARN
    """

    def __init__(self, arn: Optional[str], comment: Optional[str]) -> None:
        self.arn: Optional[str] = arn
        self.comment: Optional[str] = comment
        self.is_user_provided: bool = bool(arn)

    def name(self) -> Optional[str]:
        """
        extracts and returns the resource name from its ARN
        Raises
        ------
        ValueError if the ARN is invalid
        """
        if not self.arn:
            return None
        arn_parts: ARNParts = ARNParts(arn=self.arn)
        return arn_parts.resource_id


class IAMUser(Resource):
    """
    Represents an AWS IAM User resource
    Attributes
    ----------
    access_key_id: Optional[str]
        holds the AccessKeyId of the credential of this IAM user, if any.
    secret_access_key: Optional[str]
        holds the SecretAccessKey of the credential of this IAM user, if any.
    """

    def __init__(
        self,
        arn: Optional[str],
        comment: Optional[str],
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ) -> None:
        self.access_key_id: Optional[str] = access_key_id
        self.secret_access_key: Optional[str] = secret_access_key
        super().__init__(arn=arn, comment=comment)


class S3Bucket(Resource):
    """
    Represents an AWS S3Bucket resource
    Attributes
    ----------
    kms_key_arn: Optional[str]
        The ARN of the KMS key used in encrypting this S3Bucket, if any.
    """

    def __init__(self, arn: Optional[str], comment: Optional[str], kms_key_arn: Optional[str] = None) -> None:
        self.kms_key_arn: Optional[str] = kms_key_arn
        super().__init__(arn=arn, comment=comment)


class ECRImageRepository(Resource):
    """Represents an AWS ECR image repository resource"""

    def __init__(self, arn: Optional[str], comment: Optional[str]) -> None:
        super().__init__(arn=arn, comment=comment)

    def get_uri(self) -> Optional[str]:
        """
        extracts and returns the URI of the given ECR image repository from its ARN
        see https://docs.aws.amazon.com/AmazonECR/latest/userguide/Registries.html
        Raises
        ------
        ValueError if the ARN is invalid
        """
        if not self.arn:
            return None
        arn_parts: ARNParts = ARNParts(self.arn)
        # ECR's resource_id contains the resource-type("resource") which is excluded from the URL
        # from docs: https://docs.aws.amazon.com/AmazonECR/latest/userguide/security_iam_service-with-iam.html
        # ECR's ARN: arn:${Partition}:ecr:${Region}:${Account}:repository/${Repository-name}
        if not arn_parts.resource_id.startswith("repository/"):
            raise ValueError(f"Invalid ECR ARN ({self.arn}), can't extract the URL from it.")
        i = len("repository/")
        repo_name = arn_parts.resource_id[i:]
        return f"{arn_parts.account_id}.dkr.ecr.{arn_parts.region}.amazonaws.com/{repo_name}"
