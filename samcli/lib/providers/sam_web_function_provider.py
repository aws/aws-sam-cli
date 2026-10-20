"""Provides the AWS::Serverless::WebFunction resources of SAM templates, and checks on them"""

import logging
from typing import Any, Dict, Iterable, Iterator, List, Optional

from samcli.commands.exceptions import UserException
from samcli.lib.cfn_language_extensions.utils import is_foreach_key
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


class WebFunctionInForEachError(UserException):
    """A Web Function with local code is generated by Fn::ForEach, which isn't supported yet."""

    def __init__(self, resources: List[str]):
        super().__init__(
            message=(
                "AWS::Serverless::WebFunction resources with local code aren't supported inside Fn::ForEach yet: "
                f"{', '.join(resources)}. Define them outside Fn::ForEach, or point their CodeUri at code that's "
                "already in S3."
            )
        )


def check_no_web_functions_in_foreach(stacks: Iterable[Stack]) -> None:
    """
    Raise WebFunctionInForEachError if a Fn::ForEach generates a Web Function with local code. Only applies to
    templates expanded locally with language extensions.
    """
    found: List[str] = []
    for stack in stacks:
        original = getattr(stack, "original_template_dict", None)
        if not isinstance(original, dict):
            continue
        for key in _web_functions_in_foreach(original.get("Resources") or {}):
            found.append(f"{stack.stack_path}/{key}" if stack.stack_path else key)
    if found:
        raise WebFunctionInForEachError(found)


def _web_functions_in_foreach(resources: Dict[str, Any], inside_foreach: bool = False) -> List[str]:
    """Keys of Web Functions with local code in Fn::ForEach blocks, including nested ones."""
    found: List[str] = []
    for key, value in resources.items():
        if is_foreach_key(key):
            # Fn::ForEach::<name>: [identifier, collection, output template]
            if isinstance(value, list) and len(value) >= 3 and isinstance(value[2], dict):  # noqa: PLR2004
                found.extend(_web_functions_in_foreach(value[2], inside_foreach=True))
            continue
        if inside_foreach and isinstance(value, dict) and value.get("Type") == AWS_SERVERLESS_WEBFUNCTION:
            if _has_local_code((value.get("Properties") or {}).get("CodeUri")):
                found.append(key)
    return found


def _has_local_code(code_uri: Any) -> bool:
    """Whether packaging uploads this CodeUri. A dict is never uploaded; None means the template's directory."""
    if code_uri is None:
        return True
    if isinstance(code_uri, str):
        return not code_uri.startswith("s3://")
    return False


def stacks_have_web_functions(stacks: Iterable[Stack], local_code_only: bool = False) -> bool:
    """
    Return True if any stack (including nested stacks) defines an AWS::Serverless::WebFunction.

    Parameters
    ----------
    stacks : Iterable[Stack]
        Stacks from SamLocalStackProvider.get_stacks
    local_code_only : bool
        Only count Web Functions with local code
    """
    for stack in stacks:
        for resource in (stack.resources or {}).values():
            if not isinstance(resource, dict) or resource.get("Type") != AWS_SERVERLESS_WEBFUNCTION:
                continue
            if not local_code_only:
                return True
            code_uri = (resource.get("Properties") or {}).get("CodeUri")
            if _has_local_code(code_uri):
                return True
    return False


def template_file_has_local_web_functions(template_file: str, language_extensions_enabled: bool = False) -> bool:
    """Whether the template or a nested stack has a Web Function with local code. False if it can't be read."""
    try:
        stacks, _ = SamLocalStackProvider.get_stacks(
            template_file, language_extensions_enabled=language_extensions_enabled
        )
        return stacks_have_web_functions(stacks, local_code_only=True)
    except Exception:  # pylint: disable=broad-except
        LOG.debug("Could not load stacks from %s to look for Web Functions", template_file, exc_info=True)
        return False
