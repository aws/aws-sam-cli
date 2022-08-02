import yaml
from typing import List
from samcli.commands.exceptions import FailedArnParseException


class FargateRunnerArnMapGenerator:
    def _get_env_var_name(self, resource_arn: str) -> str:
        """
        Generates a valid environment variable name from a given resource ARN.

        Environment variable names will be the resource name with an underscore prepended, all dashes replaced by underscores, and in all upper case.

        e.g. `arn:aws:lambda:us-east-1:123456789012:function:my-lambda-function` => `_MY_LAMBDA_FUNCTION`

        Parameters
        ----------
        resource_arn : str
            The string of the resource arn from which the resource name is extracted and the environment variable name is created.

        Returns
        -------
        str
            An environment variable name representative of the resource name.

        Raises
        ------
        FailedArnParseException
            If a resource name/id could not be extracted from the resource_arn.

            NOTE: https://docs.aws.amazon.com/quicksight/latest/APIReference/qs-arn-format.html
        """

        # Extract resource-id from ARN
        # Cases:
        # 1) arn:partition:service:region:account-id:resource-id
        # 2) arn:partition:service:region:account-id:resource-type/resource-id
        # 3) arn:partition:service:region:account-id:resource-type:resource-id
        components = resource_arn.split(":")

        if len(components) < 5:
            raise FailedArnParseException(f"Failed to parse {resource_arn}, too few colon separated components.")

        resource = components[5] if len(components) == 6 else components[6]

        if "/" in resource:
            last_slash = resource.rindex("/")
            resource_id = resource[last_slash + 1 :]

        else:
            resource_id = resource

        # Format the resource-id into a valid environment variable name
        # Replace dashes and prepend an underscore in case the name starts with a number
        # e.g. 'my-resource-name' => "_MY_RESOURCE_NAME"

        env_var_name = "_" + resource_id.replace("-", "_").upper()
        return env_var_name

    def generate_env_vars_yaml_string(self, resource_arn_list: List[str]) -> str:
        """
        Generates a dictionary in the form of a YAML string mapping an environment variable name representative of a resource name to that resource ARN, for each ARN in the supplied list of resource ARNs.

        Environment variable names will be the resource name with an underscore prepended, all dashes replaced by underscores, and in all upper case.

        e.g. `arn:aws:lambda:us-east-1:123456789012:function:my-lambda-function` => `_MY_LAMBDA_FUNCTION`

        Thus, an example mapping would look like: `_MY_LAMBDA_FUNCTION : 'arn:aws:lambda:us-east-1:123456789012:function:my-lambda-function'`

        Parameters
        ----------
        resource_arn_list : List[str]
            A list of resource ARNs. For each arn, a mapping is created.

        Returns
        -------
        str
            A dictionary in the form of a YAML string holding a mapping of an environment variable name representative of a resource name to that resource ARN, for each ARN in the supplied list of resource ARNs.

        Raises
        ------
        FailedArnParseException
        If a resource name/id could not be extracted from any of the supplied resource_arns

            NOTE: https://docs.aws.amazon.com/quicksight/latest/APIReference/qs-arn-format.html

        """

        env_vars_map = {}

        for arn in resource_arn_list:
            env_var_name = self._get_env_var_name(arn)
            env_vars_map[env_var_name] = arn

        return yaml.safe_dump(env_vars_map)
