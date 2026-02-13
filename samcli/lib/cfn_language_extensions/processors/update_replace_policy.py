"""
UpdateReplacePolicy processor for CloudFormation Language Extensions.

This module provides the UpdateReplacePolicyProcessor which validates and resolves
UpdateReplacePolicy attributes on CloudFormation resources.

Requirements:
    - 7.2: WHEN a resource has an UpdateReplacePolicy attribute, THEN THE Processor
           SHALL resolve any parameter references in the policy value
    - 7.3: WHEN UpdateReplacePolicy contains a Ref to a parameter, THEN THE Processor
           SHALL substitute the parameter's value
    - 7.4: WHEN UpdateReplacePolicy resolves to AWS::NoValue, THEN THE Processor
           SHALL raise an Invalid_Template_Exception
    - 7.5: WHEN UpdateReplacePolicy does not resolve to a valid string value, THEN
           THE Processor SHALL raise an Invalid_Template_Exception
"""

from samcli.lib.cfn_language_extensions.processors.resource_policy import ResourcePolicyProcessor


class UpdateReplacePolicyProcessor(ResourcePolicyProcessor):
    """
    Validates and resolves UpdateReplacePolicy attributes on resources.

    Valid UpdateReplacePolicy values are: "Delete", "Retain", "Snapshot"

    Example:
        >>> processor = UpdateReplacePolicyProcessor()
        >>> context = TemplateProcessingContext(
        ...     fragment={
        ...         "Resources": {
        ...             "MyBucket": {
        ...                 "Type": "AWS::S3::Bucket",
        ...                 "UpdateReplacePolicy": {"Ref": "PolicyParam"}
        ...             }
        ...         }
        ...     },
        ...     parameter_values={"PolicyParam": "Retain"}
        ... )
        >>> processor.process_template(context)
        >>> print(context.fragment["Resources"]["MyBucket"]["UpdateReplacePolicy"])
        "Retain"
    """

    POLICY_NAME = "UpdateReplacePolicy"
