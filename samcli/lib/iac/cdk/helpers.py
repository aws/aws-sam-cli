"""
CDK IaC helpers functions
"""
import re
import logging
from typing import (
    Dict,
    Optional,
    Pattern,
)
from collections.abc import Mapping
from samcli.lib.iac.cdk.constants import CDK_PATH_DELIMITER

LOG = logging.getLogger(__name__)
CDK_PATH_DELIMITER = "/"


def nested_stack_resource_path_to_short_path(nested_stack_path: str) -> str:
    """
    return short path for given nested stack resource path
    Example:
        Root/NS1/NS2.NestedStack/NS2.NestedStackResource -> Root/NS1/NS2
    """
    needed_path_parts = nested_stack_path.split(CDK_PATH_DELIMITER)[:-1]
    needed_path_parts[-1] = needed_path_parts[-1].rsplit(".NestedStack", 1)[0]
    return CDK_PATH_DELIMITER.join(needed_path_parts)


def get_nested_stack_asset_id(nested_stack_resource: Dict) -> Optional[str]:
    """
    return the asset id of a nested stack resource on a best effort basis
    NOTE: The purpose of getting the asset id is to find the nested stack template
    Once the resource metadata ("aws:asset:path" and "aws:asset:property") is available under Metadata,
    we can remove this.

    Example of input:
    {
        "Type": "AWS::CloudFormation::Stack",
        "Properties": {
            "TemplateURL": {
                "Fn::Join": [
                    "",
                    [
                        "https://s3.",
                        {
                            "Ref": "AWS::Region"
                        },
                        ".",
                        {
                            "Ref": "AWS::URLSuffix"
                        },
                        "/",
                        {
                            "Ref": "AssetParametersd50fd0190033e11e0cf80e5e096c16fefedd837d96aeda2d5f8e9656b834fde4S3Bucket48EAB776"
                        },
                        "/",
                        {
                            "Fn::Select": [
                                0,
                                {
                                    "Fn::Split": [
                                        "||",
                                        {
                                            "Ref": "AssetParametersd50fd0190033e11e0cf80e5e096c16fefedd837d96aeda2d5f8e9656b834fde4S3VersionKey9812FC45"
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "Fn::Select": [
                                1,
                                {
                                    "Fn::Split": [
                                        "||",
                                        {
                                            "Ref": "AssetParametersd50fd0190033e11e0cf80e5e096c16fefedd837d96aeda2d5f8e9656b834fde4S3VersionKey9812FC45"
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                ]
            },
            "Parameters": {
                "referencetoRAssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3Bucket80092B86Ref": {
                    "Ref": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3BucketDD3A7E9A"
                },
                "referencetoRAssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3VersionKeyC9C9A588Ref": {
                    "Ref": "AssetParameters97bd9d4f97345f890d541646ecd5ec0348b62d5618cedfd76a6f6dc94f2e4f0eS3VersionKeyCEC49660"
                },
                "referencetoRAssetParametersf7d2f89c804f1cf09b90ea05ad10131e01a2a2ad020920c5afe1cdac1cd1b4feS3Bucket6802DFEERef": {
                    "Ref": "AssetParametersf7d2f89c804f1cf09b90ea05ad10131e01a2a2ad020920c5afe1cdac1cd1b4feS3BucketDACC3599"
                },
                "referencetoRAssetParametersf7d2f89c804f1cf09b90ea05ad10131e01a2a2ad020920c5afe1cdac1cd1b4feS3VersionKey3B5CD906Ref": {
                    "Ref": "AssetParametersf7d2f89c804f1cf09b90ea05ad10131e01a2a2ad020920c5afe1cdac1cd1b4feS3VersionKey7D399835"
                },
                "referencetoRAssetParameters30c6113c6df1cbcad29b046c57a169ed4e09b8b3986eb9e75d8a931827bfa95eS3Bucket4E611C73Ref": {
                    "Ref": "AssetParameters30c6113c6df1cbcad29b046c57a169ed4e09b8b3986eb9e75d8a931827bfa95eS3BucketE83B18CF"
                },
                "referencetoRAssetParameters30c6113c6df1cbcad29b046c57a169ed4e09b8b3986eb9e75d8a931827bfa95eS3VersionKey7EC253C4Ref": {
                    "Ref": "AssetParameters30c6113c6df1cbcad29b046c57a169ed4e09b8b3986eb9e75d8a931827bfa95eS3VersionKey7613286D"
                }
            }
        },
        "UpdateReplacePolicy": "Delete",
        "DeletionPolicy": "Delete",
        "Metadata": {
            "aws:cdk:path": "R/R.NestedStack/R.NestedStackResource"
        }
    }

    Output: "d50fd0190033e11e0cf80e5e096c16fefedd837d96aeda2d5f8e9656b834fde4"
    """  # pylint: disable=line-too-long
    param_pattern = re.compile("AssetParameters([0-9a-f]{64})S3Bucket")
    template_url = nested_stack_resource.get("Properties", {}).get("TemplateURL")
    if not template_url or not isinstance(template_url, Mapping):
        # None or not an intrinsic
        return None
    try:
        return _lookup(param_pattern, template_url["Fn::Join"])
    except KeyError:
        # not an intrinsic
        return None


def get_container_asset_id(lambda_function_resource: Dict) -> Optional[str]:
    """
    return the asset id of a nested stack resource on a best effort basis
    NOTE: The purpose of getting the asset id is to find the nested stack template
    Once the resource metadata ("aws:asset:path" and "aws:asset:property") is available under Metadata,
    we can remove this.

    Example of input:
    {
        "Type": "AWS::Lambda::Function",
        "Properties": {
            "Code": {
                "ImageUri": {
                    "Fn::Join": [
                    "",
                    [
                        {
                        "Ref": "AWS::AccountId"
                        },
                        ".dkr.ecr.",
                        {
                        "Ref": "AWS::Region"
                        },
                        ".",
                        {
                        "Ref": "AWS::URLSuffix"
                        },
                        "/aws-cdk/assets:8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e"
                    ]
                    ]
                }
            },
            "Role": {
            "Fn::GetAtt": [
                "ServiceRole6371A67B",
                "Arn"
            ]
            },
            "ImageConfig": {
            "Command": [
                "app.get"
            ],
            "EntryPoint": [
                "/lambda-entrypoint.sh"
            ]
            },
            "PackageType": "Image"
        },
        "DependsOn": [
            "ServiceRole6371A67B"
        ],
        "Metadata": {
            "aws:cdk:path": "R/Resource/Resource"
        }
    }

    Output: "8db62da8c9a661a051169ec5710e7c48e471f6eb556b9d853c77e0efd9689d7e"
    """
    param_pattern = re.compile(":([0-9a-f]{64})$")
    image_uri = lambda_function_resource.get("Properties", {}).get("Code", {}).get("ImageUri")
    if not image_uri or not isinstance(image_uri, Mapping):
        # not an intrinsic
        return None
    try:
        return _lookup(param_pattern, image_uri["Fn::Join"])
    except KeyError:
        # not a valid intrinsic
        return None


def _lookup(pattern: Pattern, fn_join: list) -> Optional[str]:
    _, values = fn_join
    # copy values to pop
    values = values[:]
    while values:
        val = values.pop(0)
        target = None
        if isinstance(val, Mapping) and "Ref" in val:
            target = val["Ref"]
        else:
            target = str(val)
        if target is not None:
            match = pattern.search(target)
            if match:
                return str(match.groups()[0])
    return None
