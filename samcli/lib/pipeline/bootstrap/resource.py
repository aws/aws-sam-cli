"""Represents AWS resource"""

from typing import Optional

from samcli.lib.utils.arn_utils import ARNParts


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
        if arn_parts.resource_type != "repository":
            raise ValueError(f"Invalid ECR ARN ({self.arn}), can't extract the URL from it.")
        repo_name = arn_parts.resource_id
        return f"{arn_parts.account_id}.dkr.ecr.{arn_parts.region}.amazonaws.com/{repo_name}"


class OidcProvider(Resource):
    """
    Represents an AWS OIDC Provider resource
    Attributes
    ----------
    client_id: str
        the client id used to authenticate the user with the OIDC provider.
    provider_url: str
        url of the OIDC provider.
    thumbprint: str
        thumbprint for the top intermediate certificate authority (CA)
         that signed the certificate used by the identity provider
    """

    def __init__(
        self,
        arn: Optional[str],
        comment: Optional[str],
        client_id: Optional[str],
        provider_url: Optional[str],
        thumbprint: Optional[str],
    ) -> None:
        self.client_id: Optional[str] = client_id
        self.provider_url: Optional[str] = provider_url
        self.thumbprint: Optional[str] = thumbprint
        super().__init__(arn=arn, comment=comment)
