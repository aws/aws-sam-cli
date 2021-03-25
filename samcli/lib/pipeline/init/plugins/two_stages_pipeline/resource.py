""" AWS resource represented by ARN"""
from typing import Optional


class Resource:
    def __init__(self, arn: str) -> None:
        self.arn: str = arn
        self.is_user_provided: bool = bool(arn)

    def name(self) -> Optional[str]:
        if self.arn:
            return self.arn.split(":")[-1]
        return None


class Deployer(Resource):
    def __init__(self, arn: str, access_key_id: Optional[str] = None, secret_access_key: Optional[str] = None) -> None:
        self.access_key_id: Optional[str] = access_key_id
        self.secret_access_key: Optional[str] = secret_access_key
        super().__init__(arn=arn)


class S3Bucket(Resource):
    def __init__(self, arn: str, kms_key_arn: Optional[str] = None) -> None:
        self.kms_key_arn: Optional[str] = kms_key_arn
        super().__init__(arn=arn)
