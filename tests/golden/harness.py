"""In-process harness for golden-template testing.

Two pipelines, each implemented as a single function:
- run_build_pipeline:   drives the real :class:`BuildContext`.
- run_package_pipeline: drives the real :class:`PackageContext`.

The harness drives the same ``BuildContext`` and ``PackageContext`` that
``sam build`` and ``sam package`` instantiate; it does not reimplement the
build / package logic itself. Two narrow stubs replace the network /
compute boundaries:

- :class:`samcli.lib.build.app_builder.ApplicationBuilder` ``.build()`` is
  replaced with a stub that returns an :class:`ApplicationBuildResult` with
  artifacts pointing at a per-resource sentinel directory under
  ``<build_dir>/__sam_golden_artifact__/<resource_full_path>``. The directory
  contains a single file whose content is the resource's full path, which
  makes the downstream content-addressed S3 URI deterministic per resource.
- :meth:`samcli.lib.package.s3_uploader.S3Uploader.upload` and
  ``upload_with_dedup`` are replaced with deterministic stubs returning
  ``s3://golden-bucket/<sha256>`` where the digest is taken over the file
  content.

After the build phase, the on-disk ``.aws-sam/build/template.yaml`` is read
back and any artifact-property string referencing a sentinel artifact
directory is rewritten to ``BUILT_ARTIFACT_PLACEHOLDER`` so the build pin is
stable across runs and machines.

This keeps the harness narrow and lets every other concern (LE expansion,
ForEach merge, Mappings generation, AWS::Include export, etc.) flow through
the real CLI code paths.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Tuple
from unittest.mock import patch

from samcli.commands.build.build_context import BuildContext
from samcli.commands.package.package_context import PackageContext
from samcli.lib.build.app_builder import ApplicationBuilder, ApplicationBuildResult
from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.cfn_language_extensions.utils import is_foreach_key
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.providers.provider import get_full_path
from samcli.lib.utils.resources import (
    RESOURCES_WITH_IMAGE_COMPONENT,
    RESOURCES_WITH_LOCAL_PATHS,
)
from samcli.yamlhelper import yaml_parse


def _to_plain_dict(value: Any) -> Any:
    """Recursively convert OrderedDict (and friends) to plain dict / list / scalar.

    ``yamlhelper.yaml_parse`` returns ``OrderedDict`` instances; downstream
    YAML serialization with ``yaml.safe_dump`` (used in
    :mod:`tests.golden.normalize`) does not know how to represent
    ``OrderedDict``. Flatten before returning so the test corpus and pin
    regenerator see plain dicts.
    """
    if isinstance(value, dict):
        return {k: _to_plain_dict(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain_dict(v) for v in value]
    return value


def _read_template_as_plain_dict(path: Path) -> Dict[str, Any]:
    """Read a YAML/JSON template from disk and return a plain dict.

    Centralizes the ``yaml_parse`` -> ``_to_plain_dict`` -> ``cast`` chain
    so the type signature stays clean for callers (mypy infers Any from
    yaml_parse otherwise).
    """
    with open(path, "r", encoding="utf-8") as f:
        parsed = _to_plain_dict(yaml_parse(f.read()))
    if not isinstance(parsed, dict):
        return {}
    return parsed


BUILT_ARTIFACT_PLACEHOLDER = "<<BUILT_ARTIFACT>>"
GOLDEN_BUCKET = "golden-bucket"

# Directory name placed under <build_dir> for the stub artifact tree. Kept
# deliberately verbose so the post-build path-rewriter can identify these
# paths unambiguously (a substring match on this prefix would be safe even
# if a real-world resource happened to share the same logical id).
_ARTIFACT_DIRNAME = "__sam_golden_artifact__"


def _stub_application_builder_build(build_dir: str) -> Any:
    """Build a stand-in for ``ApplicationBuilder.build``.

    The returned function captures ``build_dir`` and writes one sentinel
    directory per buildable function / layer:

      <build_dir>/__sam_golden_artifact__/<full_path>/__golden_placeholder__

    The placeholder file's content is the resource's full path, which makes
    the package phase's content-addressed S3 URI distinct per resource even
    though no real source code was compiled.

    The returned ``ApplicationBuildResult.artifacts`` map is keyed on
    ``get_full_path(stack_path, function_id)`` exactly as real SAM CLI does;
    ``BuildContext._handle_build_post_processing`` reads this map.
    """

    def _fake_build(self: ApplicationBuilder) -> ApplicationBuildResult:
        artifacts: Dict[str, str] = {}
        sentinel_root = Path(build_dir) / _ARTIFACT_DIRNAME

        for function in self._resources_to_build.functions:  # type: ignore[attr-defined]
            full_path = get_full_path(function.stack_path, function.function_id)
            artifact_dir = sentinel_root / full_path.replace("/", os.sep)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "__golden_placeholder__").write_text(full_path, encoding="utf-8")
            artifacts[full_path] = str(artifact_dir)

        for layer in self._resources_to_build.layers:  # type: ignore[attr-defined]
            full_path = layer.full_path
            artifact_dir = sentinel_root / full_path.replace("/", os.sep)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "__golden_placeholder__").write_text(full_path, encoding="utf-8")
            artifacts[full_path] = str(artifact_dir)

        return ApplicationBuildResult(BuildGraph(self._build_dir), artifacts)  # type: ignore[attr-defined]

    return _fake_build


def _fake_s3_upload(self: S3Uploader, file_name: str, key: Optional[str] = None) -> str:
    """Deterministic ``S3Uploader.upload`` replacement.

    Hashes the file content so two different inputs produce two different
    URIs, but identical content always produces the same URI. The bucket
    name is fixed to :data:`GOLDEN_BUCKET` regardless of the uploader's own
    bucket attribute so pinned outputs do not depend on local config.

    Zip files (the common artifact shape `sam package` uploads) are hashed
    over a normalized representation — sorted member names plus each
    member's content sha256 — instead of the raw zip bytes. Raw zip bytes
    embed OS-specific metadata (DOS timestamps, Unix mode bits, sometimes
    path separators) which would otherwise produce different digests on
    Windows vs. POSIX runners.
    """
    digest = _hash_zip_normalized(file_name) if _looks_like_zip(file_name) else _hash_raw_bytes(file_name)
    return f"s3://{GOLDEN_BUCKET}/{digest}"


def _looks_like_zip(file_name: str) -> bool:
    """True if ``file_name`` looks like a zip-format artifact."""
    try:
        return zipfile.is_zipfile(file_name)
    except OSError:
        return False


def _hash_raw_bytes(file_name: str) -> str:
    with open(file_name, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _hash_zip_normalized(file_name: str) -> str:
    """Hash a zip file by its sorted member names + per-member content hashes.

    This skips the zip envelope metadata (DOS timestamps, Unix permission
    bits, central directory ordering) that varies by OS and makes raw
    byte-level hashes non-deterministic across runners.
    """
    hasher = hashlib.sha256()
    with zipfile.ZipFile(file_name, "r") as zf:
        for name in sorted(zf.namelist()):
            hasher.update(name.encode("utf-8"))
            hasher.update(b"\x00")
            with zf.open(name) as member:
                hasher.update(hashlib.sha256(member.read()).digest())
    return hasher.hexdigest()


def _fake_s3_upload_with_dedup(
    self: S3Uploader,
    file_name: str,
    extension: Optional[str] = None,
    precomputed_md5: Optional[str] = None,
) -> str:
    return _fake_s3_upload(self, file_name)


def _walk_artifact_string_values(template: Dict[str, Any]):
    """Yield ``(setter, value)`` for every artifact-property string in the template.

    ``setter`` is a callable that, given a new value, replaces the original
    in place. We use this to swap built-artifact relative paths for the
    sentinel placeholder string without having to re-parse the YAML.

    The walk handles both top-level resources and resources nested inside
    ``Fn::ForEach::*`` bodies.
    """
    resources = template.get("Resources", {}) or {}
    for resource_key, resource_value in resources.items():
        if is_foreach_key(resource_key):
            yield from _walk_foreach_artifact_strings(resource_value)
            continue
        yield from _walk_resource_artifact_strings(resource_value)


def _walk_foreach_artifact_strings(foreach_value: Any):
    if not isinstance(foreach_value, list) or len(foreach_value) < 3:  # noqa: PLR2004
        return
    body = foreach_value[2]
    if not isinstance(body, dict):
        return
    for body_key, body_value in body.items():
        if is_foreach_key(body_key):
            yield from _walk_foreach_artifact_strings(body_value)
            continue
        yield from _walk_resource_artifact_strings(body_value)


def _walk_resource_artifact_strings(resource: Any):
    if not isinstance(resource, dict):
        return
    rtype = resource.get("Type")
    if not isinstance(rtype, str):
        return
    properties = resource.get("Properties")
    if not isinstance(properties, dict):
        return
    for paths_dict in (RESOURCES_WITH_LOCAL_PATHS, RESOURCES_WITH_IMAGE_COMPONENT):
        for prop_path in paths_dict.get(rtype, []):
            yield from _yield_at_path(properties, prop_path.split("."))


def _yield_at_path(container: Any, parts):
    if not isinstance(container, dict) or not parts:
        return
    head, rest = parts[0], parts[1:]
    if head not in container:
        return
    if not rest:
        value = container[head]
        if isinstance(value, str):

            def _set(new_value, _container=container, _head=head):
                _container[_head] = new_value

            yield _set, value
        return
    yield from _yield_at_path(container[head], rest)


def _replace_artifact_paths_with_placeholder(template: Dict[str, Any], build_dir: str) -> None:
    """Rewrite every artifact-property string that resolves under the sentinel
    directory to :data:`BUILT_ARTIFACT_PLACEHOLDER`.

    A value is considered an artifact path if, when joined relative to
    ``build_dir``, it lands inside ``<build_dir>/__sam_golden_artifact__/``.
    Both relative and absolute forms are recognized, which covers the two
    paths SAM CLI may write (``move_template`` rewrites relative; an
    absolute path survives if Windows cross-drive logic kicked in).
    """
    sentinel_root = (Path(build_dir) / _ARTIFACT_DIRNAME).resolve()
    for setter, value in _walk_artifact_string_values(template):
        if not isinstance(value, str):
            continue
        # Plain string artifact location can be either relative (to build_dir)
        # or absolute. Resolve once against build_dir to handle both shapes.
        candidate = (Path(build_dir) / value).resolve() if not os.path.isabs(value) else Path(value).resolve()
        try:
            candidate.relative_to(sentinel_root)
        except ValueError:
            continue
        setter(BUILT_ARTIFACT_PLACEHOLDER)


def run_build_pipeline_to_dir(
    template_path: Path,
    language_extensions: bool,
    build_dir: Path,
    cache_dir: Path,
) -> Dict[str, Any]:
    """Drive ``BuildContext`` to produce a built template under ``build_dir``.

    Returns the parsed dict read back from
    ``<build_dir>/template.yaml``. The on-disk file is left in place so
    callers (notably :func:`run_package_pipeline`) can hand the path to
    ``PackageContext`` directly.
    """
    case_dir = template_path.parent
    bctx = BuildContext(
        resource_identifier=None,
        template_file=str(template_path),
        base_dir=str(case_dir),
        build_dir=str(build_dir),
        cache_dir=str(cache_dir),
        cached=False,
        parallel=False,
        mode=None,
        aws_region="us-east-1",
        print_success_message=False,
        language_extensions=language_extensions,
    )

    fake_build = _stub_application_builder_build(str(build_dir))
    with bctx:
        with patch.object(ApplicationBuilder, "build", fake_build):
            bctx.run()

    template = _read_template_as_plain_dict(build_dir / "template.yaml")
    _replace_artifact_paths_with_placeholder(template, str(build_dir))
    return template


def run_build_pipeline(template_path: Path, language_extensions: bool) -> Dict[str, Any]:
    """In-process equivalent of ``sam build`` for a single template.

    Allocates a fresh temp dir for the build / cache outputs, drives
    :class:`BuildContext` end-to-end, post-processes the on-disk
    ``template.yaml`` to substitute the artifact placeholder, and returns
    the parsed dict.
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        build_dir = tmp_path / ".aws-sam" / "build"
        cache_dir = tmp_path / ".aws-sam" / "cache"
        return run_build_pipeline_to_dir(template_path, language_extensions, build_dir, cache_dir)


def run_package_pipeline(template_path: Path, language_extensions: bool) -> Dict[str, Any]:
    """In-process equivalent of ``sam package``.

    Runs the build pipeline first to produce a real on-disk
    ``.aws-sam/build/template.yaml`` (with artifact directories that the
    :class:`Template` exporter can actually read), then drives
    :class:`PackageContext` against that template. The S3 uploader is
    stubbed for determinism; everything else (LE expansion, ForEach merge,
    Mappings generation, AWS::Include export) runs through real code.
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        build_dir = tmp_path / ".aws-sam" / "build"
        cache_dir = tmp_path / ".aws-sam" / "cache"

        # Re-run the build phase so we have a freshly built template on
        # disk that PackageContext can read. We can't reuse a previously
        # produced dict because PackageContext re-loads the template from
        # the path itself.
        run_build_pipeline_to_dir(template_path, language_extensions, build_dir, cache_dir)

        built_template_path = build_dir / "template.yaml"
        output_template_path = tmp_path / "packaged" / "template.yaml"
        output_template_path.parent.mkdir(parents=True, exist_ok=True)

        pctx = PackageContext(
            template_file=str(built_template_path),
            s3_bucket=GOLDEN_BUCKET,
            image_repository=None,
            image_repositories=None,
            s3_prefix=None,
            kms_key_id=None,
            output_template_file=str(output_template_path),
            use_json=False,
            force_upload=False,
            no_progressbar=True,
            metadata=None,
            region="us-east-1",
            profile=None,
            language_extensions=language_extensions,
        )

        with (
            patch.object(S3Uploader, "upload", _fake_s3_upload),
            patch.object(S3Uploader, "upload_with_dedup", _fake_s3_upload_with_dedup),
        ):
            pctx.run()

        return _read_template_as_plain_dict(output_template_path)


# --- compatibility helpers used by callers ----------------------------------


def run_build_and_package(template_path: Path, language_extensions: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Convenience: produce both pins from a single build.

    Saves work for callers (``update_goldens`` and ``test_corpus``) that
    need both pins for the same template; PackageContext relies on a real
    on-disk built template, so we reuse the one from the build phase.
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        build_dir = tmp_path / ".aws-sam" / "build"
        cache_dir = tmp_path / ".aws-sam" / "cache"
        build_dict = run_build_pipeline_to_dir(template_path, language_extensions, build_dir, cache_dir)

        built_template_path = build_dir / "template.yaml"
        output_template_path = tmp_path / "packaged" / "template.yaml"
        output_template_path.parent.mkdir(parents=True, exist_ok=True)

        pctx = PackageContext(
            template_file=str(built_template_path),
            s3_bucket=GOLDEN_BUCKET,
            image_repository=None,
            image_repositories=None,
            s3_prefix=None,
            kms_key_id=None,
            output_template_file=str(output_template_path),
            use_json=False,
            force_upload=False,
            no_progressbar=True,
            metadata=None,
            region="us-east-1",
            profile=None,
            language_extensions=language_extensions,
        )

        with (
            patch.object(S3Uploader, "upload", _fake_s3_upload),
            patch.object(S3Uploader, "upload_with_dedup", _fake_s3_upload_with_dedup),
        ):
            pctx.run()

        pkg_dict = _read_template_as_plain_dict(output_template_path)
        return build_dict, pkg_dict
