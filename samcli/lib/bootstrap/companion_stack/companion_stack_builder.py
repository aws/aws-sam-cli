"""
    Companion stack template builder
"""
from typing import Dict

# pylint: disable=W0402
from string import Template

from samcli.lib.bootstrap.companion_stack.data_types import CompanionStack, ECRRepo
from samcli import __version__ as VERSION

_STACK_TEMPLATE = Template(
    """
AWSTemplateFormatVersion : '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: AWS SAM CLI Managed ECR Repo Stack
Metadata:
  SamCliInfo: $sam_cli_version
  CompanionStackname:  $companion_stack_name

Resources:
$resources
Outputs:
$outputs
"""
)

_REPO_TEMPLATE = Template(
    """
  $repo_logical_id:
    Type: AWS::ECR::Repository
    Properties:
      RepositoryName: $repo_name
      Tags:
        - Key: ManagedStackSource
          Value: AwsSamCli
        - Key: AwsSamCliCompanionStack
          Value: $companion_stack_name

      RepositoryPolicyText:
        Version: "2012-10-17"
        Statement:
          -
            Sid: AllowLambdaSLR
            Effect: Allow
            Principal:
              Service:
                - "lambda.amazonaws.com"
            Action:
                - "ecr:GetDownloadUrlForLayer"
                - "ecr:GetRepositoryPolicy"
                - "ecr:BatchGetImage"
"""
)

_OUTPUT_TEMPLATE = Template(
    """
  $repo_output_logical_id:
    Value: !Sub $${AWS::AccountId}.dkr.ecr.$${AWS::Region}.$${AWS::URLSuffix}/$${$repo_logical_id}
"""
)


class CompanionStackBuilder:
    _parent_stack_name: str
    _companion_stack: CompanionStack
    _repo_mapping: Dict[str, ECRRepo]

    def __init__(self, companion_stack: CompanionStack) -> None:
        self._companion_stack = companion_stack
        self._repo_mapping: Dict[str, ECRRepo] = dict()

    def add_function(self, function_logical_id: str) -> None:
        self._repo_mapping[function_logical_id] = ECRRepo(self._companion_stack, function_logical_id)

    def clear_functions(self) -> None:
        self._repo_mapping = dict()

    def build(self) -> str:
        repo_templates = list()
        repo_output_templates = list()
        companion_stack_name = self._companion_stack.stack_name
        for _, ecr_repo in self._repo_mapping.items():
            repo_logical_id = ecr_repo.logical_id
            repo_name = ecr_repo.physical_id
            repo_output_logical_id = ecr_repo.output_logical_id

            repo_template = _REPO_TEMPLATE.substitute(
                repo_logical_id=repo_logical_id, repo_name=repo_name, companion_stack_name=companion_stack_name
            )
            repo_templates.append(repo_template)
            repo_output_template = _OUTPUT_TEMPLATE.substitute(
                repo_output_logical_id=repo_output_logical_id, repo_logical_id=repo_logical_id
            )
            repo_output_templates.append(repo_output_template)
        repo_templates_string = "".join(repo_templates)
        repo_output_templates_string = "".join(repo_output_templates)

        stack_template_string = _STACK_TEMPLATE.substitute(
            sam_cli_version=VERSION,
            companion_stack_name=companion_stack_name,
            resources=repo_templates_string,
            outputs=repo_output_templates_string,
        )

        return stack_template_string

    @property
    def repo_mapping(self) -> Dict[str, ECRRepo]:
        return self._repo_mapping
