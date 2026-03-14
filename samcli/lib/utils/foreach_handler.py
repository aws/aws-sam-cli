"""
Utility functions for handling CloudFormation Fn::ForEach intrinsic function
"""
import copy
import logging
from typing import Dict, Tuple

LOG = logging.getLogger(__name__)


def filter_foreach_constructs(template: Dict) -> Tuple[Dict, Dict]:
    """
    Filter out Fn::ForEach constructs from template before SAM transformation.
    CloudFormation will handle these server-side during deployment.
    
    Parameters
    ----------
    template : Dict
        The SAM/CloudFormation template dictionary
    
    Returns
    -------
    Tuple[Dict, Dict]
        (template_without_foreach, foreach_constructs_dict)
        
    Notes
    -----
    Fn::ForEach constructs are identified by resource IDs starting with "Fn::ForEach::"
    These constructs are lists, not dicts, and would cause parsing errors if processed locally.
    CloudFormation expands them server-side during deployment.
    """
    template_copy = copy.deepcopy(template)
    resources = template_copy.get("Resources", {})
    
    # If no Resources section, nothing to filter
    if not resources:
        return template_copy, {}
    
    # Separate Fn::ForEach constructs from regular resources
    foreach_constructs = {}
    regular_resources = {}
    
    for resource_id, resource in resources.items():
        if resource_id.startswith("Fn::ForEach::"):
            foreach_constructs[resource_id] = resource
            LOG.info(
                f"Detected Fn::ForEach construct '{resource_id}'. "
                "This will be expanded by CloudFormation during deployment."
            )
        else:
            regular_resources[resource_id] = resource
    
    # If template only has ForEach constructs, add a placeholder resource
    # to satisfy SAM Translator's requirement for non-empty Resources section
    if not regular_resources and foreach_constructs:
        regular_resources["__PlaceholderForForEachOnly"] = {
            "Type": "AWS::CloudFormation::WaitConditionHandle",
            "Properties": {},
        }
        LOG.debug("Added placeholder resource since template only contains Fn::ForEach constructs")
    
    # Only update Resources if there were any ForEach constructs
    if foreach_constructs:
        template_copy["Resources"] = regular_resources
    
    return template_copy, foreach_constructs