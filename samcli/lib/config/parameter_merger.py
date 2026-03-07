"""
Parameter merging utilities for SAM CLI configuration
"""

import logging
from typing import Dict, Optional

LOG = logging.getLogger(__name__)


class ParameterMerger:
    """
    Handles parameter merging with precedence rules: CLI > file > config > default
    Follows existing SAM CLI patterns for parameter processing
    """

    @staticmethod
    def merge_parameters(
        config_params: Optional[Dict] = None,
        cli_params: Optional[Dict] = None,
        file_params: Optional[Dict] = None,
    ) -> Dict:
        """
        Merge parameters with precedence rules.

        Precedence (highest to lowest):
        1. CLI parameters (--parameter-overrides)
        2. File parameters (--parameter-overrides file://params.json)
        3. Config parameters ([env.command.parameters.template_parameters])

        Parameters
        ----------
        config_params : Dict, optional
            Parameters from samconfig.toml template_parameters section
        cli_params : Dict, optional
            Parameters from CLI --parameter-overrides
        file_params : Dict, optional
            Parameters loaded from external files

        Returns
        -------
        Dict
            Merged parameter dictionary with CLI taking precedence
        """
        merged = {}

        # Start with config parameters (lowest precedence)
        if config_params:
            merged.update(config_params)
            LOG.debug(f"Added config parameters: {list(config_params.keys())}")

        # Add file parameters (medium precedence)
        if file_params:
            merged.update(file_params)
            LOG.debug(f"Added file parameters: {list(file_params.keys())}")

        # Add CLI parameters (highest precedence)
        if cli_params:
            merged.update(cli_params)
            LOG.debug(f"Added CLI parameters: {list(cli_params.keys())}")

        LOG.debug(f"Final merged parameters: {list(merged.keys())}")
        return merged

    @staticmethod
    def merge_tags(
        config_tags: Optional[Dict] = None,
        cli_tags: Optional[Dict] = None,
        file_tags: Optional[Dict] = None,
    ) -> Dict:
        """
        Merge tags with same precedence rules as parameters.

        Precedence (highest to lowest):
        1. CLI tags (--tags)
        2. File tags (--tags file://tags.json)
        3. Config tags ([env.command.parameters.template_tags])

        Parameters
        ----------
        config_tags : Dict, optional
            Tags from samconfig.toml template_tags section
        cli_tags : Dict, optional
            Tags from CLI --tags
        file_tags : Dict, optional
            Tags loaded from external files

        Returns
        -------
        Dict
            Merged tag dictionary with CLI taking precedence
        """
        merged = {}

        # Start with config tags (lowest precedence)
        if config_tags:
            merged.update(config_tags)
            LOG.debug(f"Added config tags: {list(config_tags.keys())}")

        # Add file tags (medium precedence)
        if file_tags:
            merged.update(file_tags)
            LOG.debug(f"Added file tags: {list(file_tags.keys())}")

        # Add CLI tags (highest precedence)
        if cli_tags:
            merged.update(cli_tags)
            LOG.debug(f"Added CLI tags: {list(cli_tags.keys())}")

        LOG.debug(f"Final merged tags: {list(merged.keys())}")
        return merged

    @staticmethod
    def format_for_cloudformation(parameters: Dict) -> Dict:
        """
        Format merged parameters for CloudFormation deployment.
        Converts our merged dict to the format expected by CloudFormation.

        Parameters
        ----------
        parameters : Dict
            Merged parameters dictionary

        Returns
        -------
        Dict
            Parameters formatted for CloudFormation (Key=Value format)
        """
        if not parameters:
            return {}

        # Convert to CloudFormation parameter format
        formatted = {}
        for key, value in parameters.items():
            # Handle different value types
            if isinstance(value, (dict, list)):
                # Convert complex types to JSON strings
                import json

                formatted[key] = json.dumps(value)
            elif value is None:
                formatted[key] = ""
            else:
                formatted[key] = str(value)

        return formatted

    @staticmethod
    def parse_legacy_parameter_string(parameter_string: str) -> Dict:
        """
        Parse legacy parameter_overrides string format.
        Handles space-separated key=value pairs with proper quoting support.

        Parameters
        ----------
        parameter_string : str
            String in format "Key1=Value1 Key2=Value2"

        Returns
        -------
        Dict
            Dictionary of parsed parameters
        """
        if not parameter_string or not isinstance(parameter_string, str):
            return {}

        params = {}
        import shlex

        try:
            # Use shlex to properly handle quoted values
            pairs = shlex.split(parameter_string)
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    params[key.strip()] = value.strip()
                else:
                    LOG.warning(f"Skipping invalid parameter format: {pair}")
        except ValueError as e:
            LOG.warning(f"Failed to parse parameter string with shlex: {e}")
            # Fall back to simple split for malformed strings
            pairs = parameter_string.split()
            for pair in pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    params[key.strip()] = value.strip()

        return params

    @staticmethod
    def validate_parameters(parameters: Dict, template_parameters: Optional[Dict] = None) -> Dict:
        """
        Validate merged parameters against template parameter definitions.

        Parameters
        ----------
        parameters : Dict
            Merged parameters to validate
        template_parameters : Dict, optional
            Template parameter definitions from CloudFormation template

        Returns
        -------
        Dict
            Validated parameters (may remove invalid ones with warnings)
        """
        if not template_parameters:
            return parameters

        validated = {}

        for key, value in parameters.items():
            if key in template_parameters:
                validated[key] = value
            else:
                LOG.warning(f"Parameter '{key}' not found in template parameters. Skipping.")

        return validated
