from typing import List, Union
from samcli.lib.utils.boto_utils import BotoProviderType


def get_image_uri(runtime: str) -> str:
    # TODO: Public ECR repositories not yet set up.
    #       When ready, public test-running image URIs will be returned corresponding to the specified runtime
    pass


def write_file(filename: str, contents: str) -> None:
    with open(filename, "w") as f:
        f.write(contents)


def query_tagging_api(tag_filters: dict, boto_client_provider: BotoProviderType) -> Union[List[str], None]:
    """
    Queries the Tagging API to retrieve the ARNs of every resource with the given tags.

    NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#get-resources

    Parameters
    ----------
    tag_filters : dict
        The tag filters to restrict output to only those resources with the given tags.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#options

    boto_client_provider : BotoProviderType
        Provides a boto3 client in order to query tagging API

    Returns
    -------
    dict
        A ResourceTagMappingList, which contains a list of resource ARNs and tags associated with each.

        NOTE: https://docs.aws.amazon.com/cli/latest/reference/resourcegroupstaggingapi/get-resources.html#output

    Raises
    ------
    botocore.ClientError
        If the `get_resources` call fails.

        See # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html#parsing-error-responses-and-catching-exceptions-from-aws-services
    """
    resource_tag_mapping_list = (
        boto_client_provider("resourcegroupstaggingapi")
        .get_resources(TagFilters=tag_filters)
        .get("ResourceTagMappingList")
    )

    return [resource.get("ResourceARN") for resource in resource_tag_mapping_list]
