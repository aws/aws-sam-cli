"""
Utils for CDK-based projects
"""

import os
from typing import Dict

CDK_METADATA_TYPE_VALUE = "AWS::CDK::Metadata"
CDK_PATH_METADATA_KEY = "aws:cdk:path"


def is_cdk_project(template: Dict) -> bool:
    """
    Check if the CFN template was produced from a CDK project

    Parameters
    ----------
    template:
        CFN template to look through

    """
    resources = template.get("Resources", {})
    cdk_project_conditions = any(
        [
            _resource_level_metadata_exists(resources),
            _cdk_path_metadata_exists(resources),
            _relevant_cdk_files_are_present(),
        ]
    )
    return cdk_project_conditions


def _resource_level_metadata_exists(resources: Dict) -> bool:
    """
    Check if there is a AWS::CDK::Metadata resource is in the resources

    Parameters
    ----------
    resources:
        Dict of resources to look through

    """
    for _, resource in resources.items():
        if resource.get("Type", "") == CDK_METADATA_TYPE_VALUE:
            return True
    return False


def _cdk_path_metadata_exists(resources: Dict) -> bool:
    """
    Check if there is an aws:cdk:path property in the metadata of any of the resources

    Parameters
    ----------
    resources:
        Dict of resources to look through

    """
    for _, resource in resources.items():
        metadata = resource.get("Metadata", {})
        if metadata and CDK_PATH_METADATA_KEY in metadata:
            return True
    return False


def _relevant_cdk_files_are_present() -> bool:
    """
    Check if there are CDK files in the cwd
    """
    relevant_cdk_files = ["manifest.json", "tree.json", "cdk.json"]
    # In case a customer runs `cdk synth --no-staging > template.yaml` the template
    # will be in the project root and it's entirely possible to find the cdk.json there
    project_files = os.listdir(os.getcwd())
    return any(cdk_file in project_files for cdk_file in relevant_cdk_files)
