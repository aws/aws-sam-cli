"""
DeletionPolicy processor for CloudFormation Language Extensions.

This module provides the DeletionPolicyProcessor which validates and resolves
DeletionPolicy attributes on CloudFormation resources.

Requirements:
    - 7.1: WHEN a resource has a DeletionPolicy attribute, THEN THE Processor
           SHALL resolve any parameter references in the policy value
    - 7.3: WHEN DeletionPolicy contains a Ref to a parameter, THEN THE Processor
           SHALL substitute the parameter's value
    - 7.4: WHEN DeletionPolicy resolves to AWS::NoValue, THEN THE Processor
           SHALL raise an Invalid_Template_Exception
    - 7.5: WHEN DeletionPolicy does not resolve to a valid string value, THEN
           THE Processor SHALL raise an Invalid_Template_Exception
"""

from samcli.lib.cfn_language_extensions.processors.resource_policy import ResourcePolicyProcessor


class DeletionPolicyProcessor(ResourcePolicyProcessor):
    """
    Validates and resolves DeletionPolicy attributes on resources.

    Valid DeletionPolicy values are: "Delete", "Retain", "Snapshot"

    Example:
        >>> processor = DeletionPolicyProcessor()
        >>> context = TemplateProcessingContext(
        ...     fragment={
        ...         "Resources": {
        ...             "MyBucket": {
        ...                 "Type": "AWS::S3::Bucket",
        ...                 "DeletionPolicy": {"Ref": "PolicyParam"}
        ...             }
        ...         }
        ...     },
        ...     parameter_values={"PolicyParam": "Retain"}
        ... )
        >>> processor.process_template(context)
        >>> print(context.fragment["Resources"]["MyBucket"]["DeletionPolicy"])
        "Retain"
    """

    POLICY_NAME = "DeletionPolicy"
