"""
    Companion stack template builder
"""
import json

from typing import Dict

from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo
from samcli import __version__ as VERSION


class CompanionStackBuilder:
    """
    CFN template builder for the companion stack
    """

    _parent_stack_name: str
    _companion_stack: CompanionStack
    _repo_mapping: Dict[str, ECRRepo]

    def __init__(self, companion_stack: CompanionStack) -> None:
        self._companion_stack = companion_stack
        self._repo_mapping: Dict[str, ECRRepo] = dict()

    def add_function(self, function_logical_id: str) -> None:
        """
        Add an ECR repo associated with the function to the companion stack template
        """
        self._repo_mapping[function_logical_id] = ECRRepo(self._companion_stack, function_logical_id)

    def clear_functions(self) -> None:
        """
        Remove all functions that need ECR repos
        """
        self._repo_mapping = dict()

    def build(self) -> str:
        """
        Build companion stack CFN template with current functions
        Returns
        -------
        str
            CFN template for companions stack
        """
        template_dict = self._build_template_dict()
        for _, ecr_repo in self._repo_mapping.items():
            template_dict["Resources"][ecr_repo.logical_id] = self._build_repo_dict(ecr_repo)
            template_dict["Outputs"][ecr_repo.output_logical_id] = CompanionStackBuilder._build_output_dict(ecr_repo)

        return json.dumps(template_dict)

    def _build_template_dict(self) -> Dict:
        """
        Build Companion stack template dictionary with Resources and Outputs not filled
        Returns
        -------
        dict
            Companion stack template dictionary
        """
        template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Description": "AWS SAM CLI Managed ECR Repo Stack",
            "Metadata": {"SamCliInfo": VERSION, "CompanionStackname": self._companion_stack.stack_name},
            "Resources": {},
            "Outputs": {},
        }
        return template

    def _build_repo_dict(self, repo: ECRRepo) -> Dict:
        """
        Build a single ECR repo resource dictionary

        Parameters
        ----------
        repo
            ECR repo that will be turned into CFN resource

        Returns
        -------
        dict
            ECR repo resource dictionary
        """
        return {
            "Type": "AWS::ECR::Repository",
            "Properties": {
                "RepositoryName": repo.physical_id,
                "Tags": [
                    {"Key": "ManagedStackSource", "Value": "AwsSamCli"},
                    {"Key": "AwsSamCliCompanionStack", "Value": self._companion_stack.stack_name},
                ],
                "RepositoryPolicyText": {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "AllowLambdaSLR",
                            "Effect": "Allow",
                            "Principal": {"Service": ["lambda.amazonaws.com"]},
                            "Action": ["ecr:GetDownloadUrlForLayer", "ecr:GetRepositoryPolicy", "ecr:BatchGetImage"],
                        }
                    ],
                },
            },
        }

    @staticmethod
    def _build_output_dict(repo: ECRRepo) -> Dict:
        """
        Build a single ECR repo output resource dictionary

        Parameters
        ----------
        repo
            ECR repo that will be turned into CFN output resource

        Returns
        -------
        dict
            ECR repo output resource dictionary
        """
        return {
            "Value": f"!Sub ${{AWS::AccountId}}.dkr.ecr.${{AWS::Region}}.${{AWS::URLSuffix}}/${{{repo.logical_id}}}"
        }

    @property
    def repo_mapping(self) -> Dict[str, ECRRepo]:
        """
        Repo mapping dictionary with key as function logical ID and value as ECRRepo object
        """
        return self._repo_mapping
