"""In-process harness for golden-template testing.

Two pipelines, each implemented as a single function:
- run_build_pipeline:   mirrors what `sam build` does to a template.
- run_package_pipeline: mirrors what `sam package` does to a built template.

Both call SAM-CLI's own entry points (no reimplementation) and substitute
deterministic placeholders for non-deterministic outputs:
- Built artifact paths -> "<<BUILT_ARTIFACT>>"
- S3 URIs -> "s3://golden-bucket/<sha256-of-content>"

Compromises (documented inline):

- The SAM transform path drives the upstream ``samtranslator.translator.translator.Translator``
  directly (the same translator ``SamTemplateValidator.get_translated_template_if_valid``
  invokes). We deliberately do not go through ``SamTranslatorWrapper.run_plugins()``
  because that only runs plugins; it does not convert ``AWS::Serverless::*`` to
  the corresponding ``AWS::*`` CloudFormation resources, which is exactly what
  the build-time golden output should reflect.
- Managed policies are resolved from an empty map. The sentinel templates (and
  most corpus cases) do not reference managed policies by name. If a future case
  introduces managed-policy references, extend this harness with an offline
  managed-policy mapping.
- Local CodeUri / DefinitionUri / ImageUri values are pre-rewritten to
  ``s3://bucket/value`` (matching ``SamTemplateValidator._replace_local_codeuri``)
  before invoking the translator, since the translator itself rejects local
  paths. The post-translate pass then rewrites those s3 URIs (and any leftover
  raw paths) to ``BUILT_ARTIFACT_PLACEHOLDER``.
- Pseudo-parameters are seeded from
  ``IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES`` so ``!Sub
  ${AWS::Region}`` etc. resolve deterministically.
- When ``language_extensions=False`` and the template carries
  ``AWS::LanguageExtensions``, the SAM transform is skipped entirely. The SAM
  transform's plugins iterate ``Resources`` expecting each value to be a dict;
  an unresolved ``Fn::ForEach::*`` key has a list value and crashes them. This
  matches the user-visible behavior of ``sam build`` on such a template
  (the LE construct is preserved verbatim for CloudFormation server-side
  expansion).

Known limitations (deferred to follow-up PRs / corpus growth):

- Image-based Lambdas / ECR artifacts: ``_packageable_replacement`` always
  rewrites ``AWS::Lambda::Function`` ``Code`` to an S3Bucket/S3Key dict and
  ``Code.ImageUri`` to an ECR URI string, but it does not enforce that
  exactly one of those properties is set on a given resource. A template
  with both shapes will be over-rewritten. No image sentinel exists yet to
  surface this — PR 2's corpus expansion will add one.
- ``_stub_local_uris_for_translator`` duplicates the rewrite logic in
  ``SamTemplateValidator._replace_local_codeuri``. The two will drift if
  upstream extends the validator's set of properties or recognized URI
  shapes. Until the harness can call the validator without pulling in
  AWS-credential side-effects (boto Session at construction time), this
  duplication is accepted.
- ``GoldenS3Uploader`` reimplements the surface ``S3Uploader`` exposes
  rather than subclassing it, to keep the harness off the boto Session
  path. If the package code starts using S3Uploader methods we have not
  stubbed, the next failure will say so. Subclassing is the cleaner long
  term fix.
- No ``AWS::Include`` sentinel: the ``_export_global_artifacts_pass`` call
  in ``run_package_pipeline`` is exercised only indirectly. A corpus case
  with ``AWS::Include`` should be added so that pass has explicit
  coverage; deferred to follow-up.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from samcli.lib.cfn_language_extensions.sam_integration import expand_language_extensions
from samcli.lib.cfn_language_extensions.utils import is_foreach_key
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.utils.resources import (
    RESOURCES_WITH_IMAGE_COMPONENT,
    RESOURCES_WITH_LOCAL_PATHS,
)

BUILT_ARTIFACT_PLACEHOLDER = "<<BUILT_ARTIFACT>>"
GOLDEN_BUCKET = "golden-bucket"


def _load_template(template_path: Path) -> Dict[str, Any]:
    with open(template_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _walk_artifact_properties(
    template: Dict[str, Any],
) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Collect (resource_id, property_path, resource_dict) for every packageable artifact."""
    results: List[Tuple[str, str, Dict[str, Any]]] = []
    resources = template.get("Resources", {}) or {}
    for resource_id, resource in resources.items():
        if not isinstance(resource, dict):
            continue
        rtype = resource.get("Type")
        if not isinstance(rtype, str):
            continue
        for prop_paths in (
            RESOURCES_WITH_LOCAL_PATHS.get(rtype, []),
            RESOURCES_WITH_IMAGE_COMPONENT.get(rtype, []),
        ):
            for prop_path in prop_paths:
                results.append((resource_id, prop_path, resource))
    return results


def _set_at_path(container: Dict[str, Any], path: str, value: Any) -> None:
    """Set a JMESPath-style dotted path on container's `Properties`."""
    props = container.setdefault("Properties", {})
    parts = path.split(".")
    cur = props
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _get_at_path(container: Dict[str, Any], path: str) -> Any:
    props = container.get("Properties", {})
    parts = path.split(".")
    cur = props
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


# Stub S3 bucket / key the SAM translator sees in place of local CodeUri
# (kept in sync with _stub_local_uris_for_translator). Any artifact property
# matching this shape after SAM transform is the artifact we want to
# normalize to BUILT_ARTIFACT_PLACEHOLDER.
_STUB_S3_BUCKET = "bucket"
_STUB_S3_KEY = "value"


def _is_stub_s3_artifact(value: Any) -> bool:
    """True if `value` is the {S3Bucket: bucket, S3Key: value} dict the SAM
    translator generates from our pre-stubbed local URI."""
    if not isinstance(value, dict):
        return False
    if value.get("S3Bucket") == _STUB_S3_BUCKET and value.get("S3Key") == _STUB_S3_KEY:
        return True
    if value.get("Bucket") == _STUB_S3_BUCKET and value.get("Key") == _STUB_S3_KEY:
        return True
    return False


def _replace_local_artifact_paths(template: Dict[str, Any]) -> None:
    """Rewrite local artifact-property values to BUILT_ARTIFACT_PLACEHOLDER.

    Two shapes are normalized:
      - Plain string values (local paths on raw CFN resources) are replaced
        with the placeholder string.
      - The post-transform Lambda Code dict ``{S3Bucket: bucket, S3Key: value}``
        — generated by the SAM translator from the pre-stubbed local CodeUri —
        is replaced with the placeholder string.

    Intrinsic function dicts (Fn::Sub, Fn::ForEach loop refs, etc.) are left
    alone; they are not artifact paths.
    """
    for _resource_id, prop_path, resource in _walk_artifact_properties(template):
        current = _get_at_path(resource, prop_path)
        if isinstance(current, str):
            _set_at_path(resource, prop_path, BUILT_ARTIFACT_PLACEHOLDER)
        elif _is_stub_s3_artifact(current):
            _set_at_path(resource, prop_path, BUILT_ARTIFACT_PLACEHOLDER)


def _has_serverless_transform(template: Dict[str, Any]) -> bool:
    transforms = template.get("Transform", [])
    if isinstance(transforms, str):
        transforms = [transforms]
    if not isinstance(transforms, list):
        return False
    for t in transforms:
        if isinstance(t, str) and t.startswith("AWS::Serverless"):
            return True
    return False


def _has_unresolved_language_extensions(template: Dict[str, Any]) -> bool:
    """True if any top-level Resources key is an Fn::ForEach::* key.

    Such a template is not safe to feed into the SAM translator, whose
    plugins expect every Resources value to be a dict.
    """
    resources = template.get("Resources", {}) or {}
    if not isinstance(resources, dict):
        return False
    return any(is_foreach_key(k) for k in resources)


def _stub_local_uris_for_translator(template: Dict[str, Any]) -> None:
    """Pre-rewrite local CodeUri / DefinitionUri / ImageUri to s3 stubs.

    The upstream Translator rejects local paths for these properties.
    SAM CLI's ``SamTemplateValidator._replace_local_codeuri`` does the
    same rewrite before invoking the Translator. We do it inline here
    so the harness can call Translator.translate() directly without
    depending on SamTemplateValidator (which also creates a boto Session
    and brings in AWS-credential side-effects).
    """
    resources = template.get("Resources", {}) or {}
    for resource_id, resource in resources.items():
        if is_foreach_key(resource_id) or not isinstance(resource, dict):
            continue
        rtype = resource.get("Type")
        props = resource.get("Properties")
        if not isinstance(props, dict):
            continue
        if rtype == "AWS::Serverless::Function":
            if isinstance(props.get("CodeUri"), str):
                props["CodeUri"] = "s3://bucket/value"
            if isinstance(props.get("ImageUri"), str):
                props["ImageUri"] = "111111111111.dkr.ecr.region.amazonaws.com/repository"
        elif rtype == "AWS::Serverless::LayerVersion":
            if isinstance(props.get("ContentUri"), str):
                props["ContentUri"] = "s3://bucket/value"
        elif rtype in (
            "AWS::Serverless::Api",
            "AWS::Serverless::HttpApi",
            "AWS::Serverless::StateMachine",
        ):
            if isinstance(props.get("DefinitionUri"), str):
                props["DefinitionUri"] = "s3://bucket/value"


def _run_sam_transform(template: Dict[str, Any], parameter_values: Dict[str, Any]) -> Dict[str, Any]:
    """Run the SAM transform on a template if it declares the SAM transform.

    Drives ``samtranslator.translator.translator.Translator.translate()`` directly
    so AWS::Serverless::* resources are converted to their AWS::* counterparts.
    Templates that don't declare the SAM transform — or that still carry
    unresolved Fn::ForEach::* keys (i.e. LE was disabled on an LE template) —
    are passed through unchanged.
    """
    if not _has_serverless_transform(template):
        return template
    if _has_unresolved_language_extensions(template):
        # Cannot safely run SAM transform on a template with unresolved
        # ForEach keys; the translator's plugins iterate Resources expecting
        # dicts. Mirror real `sam build` behavior by leaving the template
        # untouched in this corner case.
        return template

    # Lazy imports keep the import graph small and let import-time errors
    # surface in the test that exercises this code path rather than at
    # module load time.
    from samtranslator.parser.parser import Parser
    from samtranslator.translator.translator import Translator

    template_copy = copy.deepcopy(template)
    _stub_local_uris_for_translator(template_copy)

    sam_translator = Translator(
        managed_policy_map=None,
        sam_parser=Parser(),
        plugins=[],
        boto_session=None,
    )

    translated: Dict[str, Any] = sam_translator.translate(
        sam_template=template_copy,
        parameter_values=parameter_values,
        get_managed_policy_map=lambda: {},
    )
    return translated


def run_build_pipeline(template_path: Path, language_extensions: bool) -> Dict[str, Any]:
    """In-process equivalent of `sam build` for one template.

    1. Load the template.
    2. Run LE expansion (no-op if disabled or template has no LE transform).
    3. Run the SAM transform on the expanded template.
    4. Replace local artifact paths with BUILT_ARTIFACT_PLACEHOLDER.
    """
    template = _load_template(template_path)

    parameter_values = dict(IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES)

    le_result = expand_language_extensions(
        template, parameter_values=parameter_values, enabled=language_extensions
    )
    expanded = copy.deepcopy(le_result.expanded_template)

    transformed = _run_sam_transform(expanded, parameter_values)
    _replace_local_artifact_paths(transformed)
    return transformed


class GoldenS3Uploader:
    """Deterministic S3Uploader stand-in.

    Implements the same interface the package code relies on:
      .upload(file_path, prefix) -> s3 URL
      .file_exists(...) -> always False (force re-upload, deterministic)
      .bucket_name -> "golden-bucket"
    """

    def __init__(self, template_dir: str):
        self._template_dir = template_dir
        self.bucket_name = GOLDEN_BUCKET
        self.no_progressbar = True

    def upload(self, file_name: str, key: Optional[str] = None) -> str:
        # Hash the file content so the URI is content-addressed.
        with open(file_name, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        return f"s3://{GOLDEN_BUCKET}/{digest}"

    def upload_with_dedup(
        self,
        file_name: str,
        extension: Optional[str] = None,
        precomputed_md5: Optional[str] = None,
    ) -> str:
        return self.upload(file_name)

    def file_exists(self, key: str) -> bool:
        return False

    def to_path_style_s3_url(self, key: str, version: Optional[str] = None) -> str:
        return f"https://s3.amazonaws.com/{GOLDEN_BUCKET}/{key}"

    def get_version_of_artifact(self, s3_url: str):
        return None


def run_package_pipeline(
    template_path: Path,
    build_output: Dict[str, Any],
) -> Dict[str, Any]:
    """In-process equivalent of `sam package` for one template + build output.

    1. Walk packageable artifact properties on the build output and replace
       each local path with an s3://golden-bucket/<sha256> URI.
    2. Run _export_global_artifacts_pass on the rewritten template to
       handle any AWS::Include structural nodes.
    3. Return the final dict.
    """
    from samcli.lib.package.artifact_exporter import _export_global_artifacts_pass

    template_dir = str(template_path.parent)
    uploader = GoldenS3Uploader(template_dir)

    # Walk build_output's artifact properties and rewrite local paths.
    pkg = copy.deepcopy(build_output)
    _rewrite_artifacts_to_s3(pkg, uploader, template_dir)

    # AWS::Include pass on the rewritten template.
    _export_global_artifacts_pass(pkg, uploader, template_dir)
    return pkg


def _rewrite_artifacts_to_s3(template: Dict[str, Any], uploader, template_dir: str) -> None:
    """For every packageable artifact property, rewrite local path or
    BUILT_ARTIFACT_PLACEHOLDER to an s3:// URI structure.

    The exact replacement shape depends on the resource type. See
    ``_packageable_replacement`` for the per-resource-type mapping. This
    walker only triggers when the current value is a plain string
    (placeholder or path) — intrinsic function dicts (Fn::Sub etc.) survive.
    """
    for resource_id, prop_path, resource in _walk_artifact_properties(template):
        current = _get_at_path(resource, prop_path)
        # Skip if not a path or placeholder; intrinsic dicts (Fn::Sub) etc. survive.
        if not isinstance(current, str):
            continue
        rtype = resource.get("Type")
        if not isinstance(rtype, str):
            # _walk_artifact_properties already filters, but re-narrow for mypy.
            continue
        replacement = _packageable_replacement(
            rtype, prop_path, current, template_dir, resource_id
        )
        _set_at_path(resource, prop_path, replacement)


def _packageable_replacement(
    rtype: str, prop_path: str, current: Any, template_dir: str, resource_id: str
) -> Any:
    """Compute the deterministic replacement for an artifact property.

    Returns either a dict ({"S3Bucket": ..., "S3Key": ...}) or a string
    ("s3://...") depending on the resource type. Sentinel: hashes
    "<current>|<rtype>|<prop_path>|<resource_id>" so each resource gets a
    distinct URI even when ``current`` is the constant
    ``BUILT_ARTIFACT_PLACEHOLDER`` after the build pass. Including
    ``resource_id`` is what makes the digest content-aware: without it,
    every Lambda Code in the corpus would collapse to the same S3Key and a
    regression that swapped two functions' artifacts would go undetected.

    Shapes covered (extend as new corpus cases require new shapes):
      - AWS::Lambda::Function .Code      -> {"S3Bucket": ..., "S3Key": ...}
      - AWS::Lambda::Function .Code.ImageUri -> "<reg>/<repo>:<tag>"
      - AWS::Serverless::Function .CodeUri (post-transform = Lambda::Function .Code, handled above)
      - All other artifact properties     -> "s3://<bucket>/<sha256>"
    """
    digest = hashlib.sha256(
        f"{current}|{rtype}|{prop_path}|{resource_id}".encode("utf-8")
    ).hexdigest()
    # Lambda image — must check before the .Code dict shape
    if rtype == "AWS::Lambda::Function" and prop_path == "Code.ImageUri":
        return f"{GOLDEN_BUCKET}.dkr.ecr.us-east-1.amazonaws.com/golden:{digest[:12]}"
    # Lambda-style dict
    if rtype == "AWS::Lambda::Function" and prop_path == "Code":
        return {"S3Bucket": GOLDEN_BUCKET, "S3Key": digest}
    # Default: s3:// URI string
    return f"s3://{GOLDEN_BUCKET}/{digest}"
