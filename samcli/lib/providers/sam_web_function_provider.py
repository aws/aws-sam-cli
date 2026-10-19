"""Provides the AWS::Serverless::WebFunction resources of SAM templates to build"""

import logging
from typing import Dict, Iterator, List, Optional

from samcli.lib.providers.exceptions import MissingFunctionNameException
from samcli.lib.providers.provider import Stack, WebFunction, get_full_path, get_function_build_info
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.packagetype import ZIP
from samcli.lib.utils.resources import AWS_SERVERLESS_WEBFUNCTION

LOG = logging.getLogger(__name__)

# Used when EntryPoint isn't set
DEFAULT_ENTRY_POINT = "index.js"


class SamWebFunctionProvider(SamBaseProvider):
    """
    Fetches the buildable AWS::Serverless::WebFunction resources of valid, normalized SAM templates. Web Functions with
    code already in S3 are skipped.
    """

    def __init__(
        self,
        stacks: List[Stack],
        use_raw_codeuri: bool = False,
        ignore_code_extraction_warnings: bool = False,
    ) -> None:
        """
        :param stacks: List of stacks Web Functions are extracted from
        :param use_raw_codeuri: Do not resolve CodeUri relative to the template path, use the raw value
        :param ignore_code_extraction_warnings: Don't log a warning for Web Functions whose code is in S3
        """
        self._stacks = stacks
        self.web_functions = SamWebFunctionProvider._extract_web_functions(
            stacks, use_raw_codeuri, ignore_code_extraction_warnings
        )

    @property
    def stacks(self) -> List[Stack]:
        return self._stacks

    def update(
        self, stacks: List[Stack], use_raw_codeuri: bool = False, ignore_code_extraction_warnings: bool = False
    ) -> None:
        """Reload the Web Functions from updated stacks"""
        self._stacks = stacks
        self.web_functions = SamWebFunctionProvider._extract_web_functions(
            stacks, use_raw_codeuri, ignore_code_extraction_warnings
        )

    def get(self, name: str) -> Optional[WebFunction]:
        """Return the Web Function matching a full path, logical ID, function ID or name (first wins), or None"""
        if not name:
            raise MissingFunctionNameException()
        if name in self.web_functions:
            return self.web_functions[name]
        matches = sorted(
            (f for f in self.get_all() if name in (f.function_id, f.name, f.functionname)),
            key=lambda f: f.full_path.lower(),
        )
        return matches[0] if matches else None

    def get_all(self) -> Iterator[WebFunction]:
        """Yield every buildable Web Function"""
        yield from self.web_functions.values()

    @staticmethod
    def _extract_web_functions(
        stacks: List[Stack], use_raw_codeuri: bool = False, ignore_code_extraction_warnings: bool = False
    ) -> Dict[str, WebFunction]:
        result: Dict[str, WebFunction] = {}
        for stack in stacks:
            for name, resource in stack.resources.items():
                if not isinstance(resource, dict) or resource.get("Type") != AWS_SERVERLESS_WEBFUNCTION:
                    continue
                properties = resource.get("Properties", {}) or {}
                if SamBaseProvider._is_s3_location(properties.get("CodeUri")):
                    if not ignore_code_extraction_warnings:
                        SamBaseProvider._warn_code_extraction(AWS_SERVERLESS_WEBFUNCTION, name, "CodeUri")
                    continue
                web_function = SamWebFunctionProvider._convert_web_function_resource(
                    stack, name, properties, resource.get("Metadata"), use_raw_codeuri
                )
                result[web_function.full_path] = web_function
        return result

    @staticmethod
    def _convert_web_function_resource(
        stack: Stack, name: str, properties: Dict, metadata: Optional[Dict], use_raw_codeuri: bool = False
    ) -> WebFunction:
        function_id = name
        if isinstance(metadata, dict) and isinstance(metadata.get("SamResourceId"), str) and metadata["SamResourceId"]:
            function_id = metadata["SamResourceId"]
        codeuri = SamBaseProvider._extract_codeuri(properties, "CodeUri")
        if codeuri and not use_raw_codeuri:
            codeuri = SamLocalStackProvider.normalize_resource_path(stack.location, codeuri)
        LOG.debug("Found Serverless web function with name='%s' and CodeUri='%s'", name, codeuri)
        return WebFunction(
            function_id=function_id,
            name=name,
            functionname=properties.get("FunctionName", name),
            runtime=properties.get("Runtime"),
            codeuri=codeuri,
            entry_point=properties.get("EntryPoint") or DEFAULT_ENTRY_POINT,
            metadata=metadata,
            function_build_info=get_function_build_info(
                get_full_path(stack.stack_path, function_id), ZIP, None, codeuri, None, metadata
            ),
            stack_path=stack.stack_path,
        )
