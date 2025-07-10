"""Helper functions to work with SAM GraphQLApi resource"""

from typing import Any, Dict, List, Tuple, Union

SCHEMA_ARTIFACT_PROPERTY = "SchemaUri"
CODE_ARTIFACT_PROPERTY = "CodeUri"


def find_all_paths_and_values(property_name: str, graphql_dict: Dict[str, Any]) -> List[Tuple[str, Union[str, Dict]]]:
    """Find paths to the all properties with property_name and their (properties) values.

    It leverages the knowledge of GraphQLApi structure instead of doing generic search in the graph.

    Parameters
    ----------
    property_name
        Name of the property to look up, for example 'CodeUri'
    graphql_dict
        GraphQLApi resource dict

    Returns
    -------
        list of tuple (path, value) for all found properties which has property_name
    """
    # need to look up only in "Resolvers" and "Functions" subtrees
    resolvers_and_functions = {k: graphql_dict[k] for k in ("Resolvers", "Functions") if k in graphql_dict}
    stack: List[Tuple[Dict[str, Any], str]] = [(resolvers_and_functions, "")]
    paths_values: List[Tuple[str, Union[str, Dict]]] = []

    while stack:
        node, path = stack.pop()
        if isinstance(node, dict):
            for key, value in node.items():
                if key == property_name:
                    paths_values.append((f"{path}{key}", value))
                elif isinstance(value, dict):
                    stack.append((value, f"{path}{key}."))
        # there is no need to handle lists because
        # paths to "CodeUri" within "Resolvers" and "Functions" doesn't have lists
    return paths_values
