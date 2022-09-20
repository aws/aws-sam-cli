from typing import List


def _clean_references_list(references: List[str]) -> List[str]:
    """
    Return a new copy of the complete references list.

    e.g. given a list of references like
    [
        'aws_lambda_layer_version.layer1[0].arn',
        'aws_lambda_layer_version.layer1[0]',
        'aws_lambda_layer_version.layer1',
    ]
    We want only the first complete reference ('aws_lambda_layer_version.layer1[0].arn')

    Parameters
    ----------
    references: List[str]
        A list of reference strings

    Returns
    -------
    List[str]
        A copy of a cleaned list of reference strings
    """
    cleaned_references = []
    references.sort(reverse=True)
    if not references:
        return []
    cleaned_references.append(references[0])
    for i in range(1, len(references)):
        if not cleaned_references[-1].startswith(references[i]):
            cleaned_references.append(references[i])
    return cleaned_references
