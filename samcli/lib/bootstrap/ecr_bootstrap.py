import re
from string import Template

from samcli.lib.utils.hash import str_checksum
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
    def __init__(self, stack_name):
        self._stack_name = stack_name
        self._functions = dict()

        self._escaped_stack_name = re.sub(r"[^a-z0-9]", "", self._stack_name.lower())
        self._stack_hash = str_checksum(self._stack_name)

    def add_function(self, function_logical_id):
        self._functions[function_logical_id] = self._get_repo_logical_id(function_logical_id)

    def build(self):
        repo_templates = list()
        repo_output_templates = list()
        companion_stack_name = self.get_companion_stack_name()
        for function_logical_id, repo_logical_id in self._functions.items():
            repo_name = self._get_repo_name(function_logical_id)
            repo_template = _REPO_TEMPLATE.substitute(
                repo_logical_id=repo_logical_id, repo_name=repo_name, companion_stack_name=companion_stack_name
            )
            repo_templates.append(repo_template)

            repo_output_logical_id = self._get_repo_output_logical_id(function_logical_id)
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
    
    def get_repo_logical_id_mapping(self):
        return self._functions

    def _get_escaped_function_logical_id(self, function_logical_id):
        return re.sub(r"[^a-z0-9]", "", function_logical_id.lower())

    def _get_function_md5(self, function_logical_id):
        return str_checksum(function_logical_id)

    def get_repo_logical_id(self, function_logical_id):
        return (
            self._get_escaped_function_logical_id(function_logical_id)[:52]
            + self._get_function_md5(function_logical_id)
            + "Repo"
        )

    def get_repo_output_logical_id(self, function_logical_id):
        return (
            self._get_escaped_function_logical_id(function_logical_id)[:52]
            + self._get_function_md5(function_logical_id)
            + "Out"
        )

    def get_repo_name(self, function_logical_id):
        return (
            self._escaped_stack_name
            + self._escaped_stack_name[:8]
            + "/"
            + self._get_escaped_function_logical_id(function_logical_id)
            + self._get_function_md5(function_logical_id)[:8]
            + "repo"
        )

    def get_companion_stack_name(self):
        return self._stack_name[:104] + "-" + self._stack_hash[:8] + "-CompanionStack"
