"""Provider for AWS::Serverless::MicrovmImage resources."""

import logging
from typing import Dict, List, Optional, Set, Tuple

from samcli.lib.providers.provider import MicrovmImage, Stack, get_full_path
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.architecture import ARM64
from samcli.lib.utils.resources import AWS_LAMBDA_MICROVMIMAGE, AWS_SERVERLESS_MICROVMIMAGE

LOG = logging.getLogger(__name__)

_MICROVMIMAGE_RESOURCE_TYPES = {AWS_SERVERLESS_MICROVMIMAGE, AWS_LAMBDA_MICROVMIMAGE}

# MicrovmImage currently only supports ARM_64.
_SUPPORTED_ARCHITECTURES = {
    "ARM_64": ARM64,
}
_DEFAULT_ARCHITECTURE = ARM64

# Metadata keys that configure a Lambda image function build. A MicrovmImage is always built from the
# Dockerfile at the root of CodeUri, as the MicroVM service builds it, so these have no effect.
_IGNORED_DOCKER_METADATA_KEYS = ("Dockerfile", "DockerContext", "DockerTag", "DockerBuildArgs")


class SamMicrovmImageProvider(SamBaseProvider):
    """Extracts MicrovmImage resources from SAM templates."""

    def __init__(
        self,
        stacks: List[Stack],
        use_raw_codeuri: bool = False,
        ignore_code_extraction_warnings: bool = False,
    ) -> None:
        self._microvm_images: List[MicrovmImage] = []
        # Images skipped at extraction: (identifiers it can be looked up by, why it was skipped)
        self._skipped_images: List[Tuple[Set[str], str]] = []
        self._use_raw_codeuri = use_raw_codeuri
        self._ignore_code_extraction_warnings = ignore_code_extraction_warnings
        self._extract_microvm_images(stacks)

    def _extract_microvm_images(self, stacks: List[Stack]) -> None:
        for stack in stacks:
            for logical_id, resource in stack.resources.items():
                resource_type = resource.get("Type")
                if resource_type not in _MICROVMIMAGE_RESOURCE_TYPES:
                    continue

                properties = resource.get("Properties", {})
                metadata = resource.get("Metadata", None)
                code_property_key = SamBaseProvider.CODE_PROPERTY_KEYS[resource_type]
                code_value = properties.get(code_property_key, "")
                # AWS::Lambda::MicrovmImage.CodeArtifact is a {"Uri": ...} structure when hand-written;
                # CDK templates arrive as a bare string after ResourceMetadataNormalizer. Accept both.
                if isinstance(code_value, dict) and "Uri" in code_value:
                    code_value = code_value["Uri"]

                # Skip resources with S3 code — not buildable locally
                if SamBaseProvider._is_s3_location(code_value):
                    if not self._ignore_code_extraction_warnings:
                        SamBaseProvider._warn_code_extraction(resource_type, logical_id, code_property_key)
                    self._record_skipped_image(
                        stack,
                        logical_id,
                        properties,
                        metadata,
                        f"{code_property_key} is an S3 location; sam build only builds a local source directory",
                    )
                    continue

                # Only extract if code_value is a non-empty local path string
                if isinstance(code_value, str) and code_value:
                    microvm_image = self._convert_microvm_image_resource(
                        stack, logical_id, code_value, properties, metadata
                    )
                    self._microvm_images.append(microvm_image)
                else:
                    LOG.warning(
                        "MicrovmImage resource '%s' has missing or invalid %s and will be skipped for build.",
                        logical_id,
                        code_property_key,
                    )
                    self._record_skipped_image(
                        stack, logical_id, properties, metadata, f"{code_property_key} is missing or invalid"
                    )

    def _record_skipped_image(
        self, stack: Stack, logical_id: str, properties: Dict, metadata: Optional[Dict], reason: str
    ) -> None:
        """Remember why an image was skipped, under the same identifiers get() accepts."""
        sam_resource_id = (metadata or {}).get("SamResourceId")
        resource_id = sam_resource_id if isinstance(sam_resource_id, str) and sam_resource_id else logical_id
        identifiers = {logical_id, resource_id, get_full_path(stack.stack_path, resource_id)}
        name = properties.get("Name")
        if isinstance(name, str) and name:
            identifiers.add(name)
        self._skipped_images.append((identifiers, reason))

    def get_skip_reason(self, name: str) -> Optional[str]:
        """
        Why the MicrovmImage with this identifier was skipped at extraction, or None if it wasn't.

        A skipped image is not returned by get(), so an explicitly targeted build can use this to report
        the real reason instead of "resource not found".
        """
        for identifiers, reason in self._skipped_images:
            if name in identifiers:
                return reason
        return None

    def _convert_microvm_image_resource(
        self,
        stack: Stack,
        logical_id: str,
        code_uri: str,
        resource_properties: Dict,
        metadata: Optional[Dict] = None,
    ) -> MicrovmImage:
        """
        Converts a MicrovmImage resource to a MicrovmImage configuration usable by the provider.

        Parameters
        ----------
        stack : Stack
            The stack the resource is defined in
        logical_id : str
            LogicalID of the resource
        code_uri : str
            Local path to the source directory containing the Dockerfile
        resource_properties : dict
            Properties of this resource
        metadata : dict
            Metadata of this resource

        Returns
        -------
        MicrovmImage
            MicrovmImage configuration
        """
        if not self._use_raw_codeuri:
            code_uri = SamLocalStackProvider.normalize_resource_path(stack.location, code_uri)

        # Extract architecture from CpuConfigurations[0].Architecture, mapping CFN's format
        # (e.g. "ARM_64") to SAM CLI's internal format (e.g. "arm64"). Defaults to arm64 when
        # CpuConfigurations is not specified, matching the only architecture supported today.
        architecture: Optional[str] = _DEFAULT_ARCHITECTURE
        cpu_configurations = resource_properties.get("CpuConfigurations", [])
        if cpu_configurations and isinstance(cpu_configurations, list) and len(cpu_configurations) > 0:
            first_config = cpu_configurations[0]
            if isinstance(first_config, dict) and "Architecture" in first_config:
                cfn_architecture = first_config.get("Architecture")
                # An unresolvable !Ref is rewritten by IntrinsicResolver to the parameter name
                # (a string), so it lands here as an unsupported value rather than a dict.
                architecture = (
                    _SUPPORTED_ARCHITECTURES.get(cfn_architecture) if isinstance(cfn_architecture, str) else None
                )
                if architecture is None:
                    LOG.warning(
                        "MicrovmImage '%s' has unsupported Architecture %r; only ARM_64 is supported. "
                        "If Architecture references a template parameter, provide its value via "
                        "--parameter-overrides.",
                        logical_id,
                        cfn_architecture,
                    )

        ignored_metadata_keys = [key for key in _IGNORED_DOCKER_METADATA_KEYS if key in (metadata or {})]
        if ignored_metadata_keys:
            LOG.warning(
                "MicrovmImage '%s' ignores Metadata %s: it is built from the Dockerfile at the root of CodeUri, "
                "as the MicroVM service builds it.",
                logical_id,
                ", ".join(ignored_metadata_keys),
            )

        return MicrovmImage(
            name=logical_id,
            microvm_image_name=resource_properties.get("Name"),
            code_uri=code_uri,
            architecture=architecture,
            stack_path=stack.stack_path,
            metadata=metadata,
        )

    def get_all(self) -> List[MicrovmImage]:
        return self._microvm_images

    def get(self, name: str) -> Optional[MicrovmImage]:
        if not name:
            return None
        # Identity fields win over Properties.Name, so one image's Name cannot shadow another's logical ID.
        for image in self._microvm_images:
            if name in (image.full_path, image.microvm_image_id, image.name):
                return image
        for image in self._microvm_images:
            if name == image.microvm_image_name:
                return image
        return None
