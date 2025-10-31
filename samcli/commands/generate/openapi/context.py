"""
Context for OpenAPI generation command execution
"""

import json
import logging
from typing import Dict, Optional, cast

import click

from samcli.commands.generate.openapi.exceptions import GenerateOpenApiException
from samcli.lib.generate.openapi_generator import OpenApiGenerator
from samcli.yamlhelper import yaml_dump

LOG = logging.getLogger(__name__)


class OpenApiContext:
    """
    Context manager for OpenAPI generation command
    """

    MSG_SUCCESS = "\nSuccessfully generated OpenAPI document{output_info}.\n"

    def __init__(
        self,
        template_file: str,
        api_logical_id: Optional[str],
        output_file: Optional[str],
        output_format: str,
        openapi_version: str,
        parameter_overrides: Optional[Dict],
        region: Optional[str],
        profile: Optional[str],
    ):
        """
        Initialize OpenAPI generation context

        Parameters
        ----------
        template_file : str
            Path to SAM template
        api_logical_id : str, optional
            API resource logical ID
        output_file : str, optional
            Output file path (None for stdout)
        output_format : str
            Output format: 'yaml' or 'json'
        openapi_version : str
            OpenAPI version: '2.0' or '3.0'
        parameter_overrides : dict, optional
            Template parameter overrides
        region : str, optional
            AWS region
        profile : str, optional
            AWS profile
        """
        self.template_file = template_file
        self.api_logical_id = api_logical_id
        self.output_file = output_file
        self.output_format = output_format
        self.openapi_version = openapi_version
        self.parameter_overrides = parameter_overrides
        self.region = region
        self.profile = profile

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):
        """
        Execute OpenAPI generation

        Raises
        ------
        GenerateOpenApiException
            If generation fails
        """
        try:
            LOG.debug(
                "Generating OpenAPI - Template: %s, API ID: %s, Format: %s",
                self.template_file,
                self.api_logical_id or "auto-detect",
                self.output_format,
            )

            # Create generator
            generator = OpenApiGenerator(
                template_file=self.template_file,
                api_logical_id=self.api_logical_id,
                parameter_overrides=self.parameter_overrides,
                region=self.region,
                profile=self.profile,
            )

            # Generate OpenAPI document
            openapi_doc = generator.generate()

            # Convert to OpenAPI 3.0 if requested
            if self.openapi_version == "3.0":
                from samcli.lib.generate.openapi_converter import OpenApiConverter

                openapi_doc = OpenApiConverter.swagger_to_openapi3(openapi_doc)

            # Format output
            output_str = self._format_output(openapi_doc)

            # Write output
            self._write_output(output_str)

            # Display success message
            self._display_success()

        except GenerateOpenApiException:
            # Re-raise our specific exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            raise GenerateOpenApiException(f"Unexpected error during OpenAPI generation: {str(e)}") from e

    def _format_output(self, openapi_doc: Dict) -> str:
        """
        Format OpenAPI document as YAML or JSON

        Parameters
        ----------
        openapi_doc : dict
            OpenAPI document

        Returns
        -------
        str
            Formatted output string
        """
        if self.output_format == "json":
            return json.dumps(openapi_doc, indent=2, ensure_ascii=False)
        else:
            # Default to YAML
            return cast(str, yaml_dump(openapi_doc))

    def _write_output(self, content: str):
        """
        Write output to file or stdout

        Parameters
        ----------
        content : str
            Content to write
        """
        if self.output_file:
            # Write to file
            try:
                with open(self.output_file, "w") as f:
                    f.write(content)
                LOG.debug("Wrote OpenAPI document to file: %s", self.output_file)
            except IOError as e:
                raise GenerateOpenApiException(f"Failed to write to file '{self.output_file}': {str(e)}") from e
        else:
            # Write to stdout
            click.echo(content)

    def _display_success(self):
        """
        Display success message to user
        """
        if self.output_file:
            output_info = f" and wrote to file: {self.output_file}"
        else:
            output_info = ""

        msg = self.MSG_SUCCESS.format(output_info=output_info)
        if self.output_file:
            # Only show success message if writing to file
            # (to not clutter stdout when piping)
            click.secho(msg, fg="green")
