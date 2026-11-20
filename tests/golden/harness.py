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
  one entry per buildable function / layer pointing at a per-resource
  artifact directory under ``<build_dir>/<resource_full_path>``. The
  directory contains a single file whose content is the resource's full
  path, which makes the downstream content-addressed S3 URI deterministic
  per resource.
- :meth:`samcli.lib.package.s3_uploader.S3Uploader.upload` and
  ``upload_with_dedup`` are replaced with deterministic stubs returning
  ``s3://golden-bucket/<sha256>`` where the digest is taken over the file
  content (zip-aware: zip envelopes are hashed by sorted member names plus
  per-member content hashes so the digest is OS-deterministic).

The case directory (``template.yaml`` + ``src/``) is staged into a fresh
temp dir before driving ``BuildContext``. Real ``sam build`` writes
``CodeUri`` as ``os.path.relpath(absolute_artifact, template_dir)``; with
the case staged into a temp tree, ``original_dir`` is the staged template's
parent and the relpath is the deterministic ``.aws-sam/build/<full_path>``
that real ``sam build`` produces. No post-build path rewriting is needed.

This keeps the harness narrow and lets every other concern (LE expansion,
ForEach merge, Mappings generation, AWS::Include export, etc.) flow through
the real CLI code paths.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Optional, Tuple
from unittest.mock import patch

from samcli.commands.build.build_context import BuildContext
from samcli.commands.package.package_context import PackageContext
from samcli.lib.build.app_builder import ApplicationBuilder, ApplicationBuildResult
from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.providers.provider import get_full_path
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


GOLDEN_BUCKET = "golden-bucket"


def _stub_application_builder_build(build_dir: str) -> Any:
    """Build a stand-in for ``ApplicationBuilder.build``.

    The returned function captures ``build_dir`` and writes one artifact
    directory per buildable function / layer at the canonical location
    real ``sam build`` uses:

      <build_dir>/<full_path>/__golden_placeholder__

    The placeholder file's content is the resource's full path, which makes
    the package phase's content-addressed S3 URI distinct per resource even
    though no real source code was compiled. ``ApplicationBuilder.update_template``
    rewrites these absolute paths to ``relpath(artifact, template_dir)``;
    when the case is staged under the temp dir before driving
    ``BuildContext``, the relpath becomes the deterministic
    ``.aws-sam/build/<full_path>`` string real ``sam build`` produces.

    The returned ``ApplicationBuildResult.artifacts`` map is keyed on
    ``get_full_path(stack_path, function_id)`` exactly as real SAM CLI does;
    ``BuildContext._handle_build_post_processing`` reads this map.
    """

    def _fake_build(self: ApplicationBuilder) -> ApplicationBuildResult:
        artifacts: Dict[str, str] = {}

        for function in self._resources_to_build.functions:  # type: ignore[attr-defined]
            full_path = get_full_path(function.stack_path, function.function_id)
            artifact_dir = Path(build_dir) / full_path.replace("/", os.sep)
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "__golden_placeholder__").write_text(full_path, encoding="utf-8")
            artifacts[full_path] = str(artifact_dir)

        for layer in self._resources_to_build.layers:  # type: ignore[attr-defined]
            full_path = layer.full_path
            artifact_dir = Path(build_dir) / full_path.replace("/", os.sep)
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


_STAGED_CASE_DIRNAME = "case"


def _stage_case_dir(case_dir: Path, tmp_root: Path) -> Path:
    """Copy the case directory (template + src/) into ``tmp_root/case``.

    Real ``sam build`` rewrites artifact paths to
    ``relpath(absolute_artifact, template_dir)``. Staging the case dir into
    a known location under the temp root makes that relpath the canonical
    deterministic ``.aws-sam/build/<full_path>`` string regardless of where
    the host's tempdir lives.
    """
    staged = tmp_root / _STAGED_CASE_DIRNAME
    shutil.copytree(case_dir, staged)
    return staged


def run_build_pipeline_to_dir(
    staged_template_path: Path,
    language_extensions: bool,
    build_dir: Path,
    cache_dir: Path,
) -> Dict[str, Any]:
    """Drive ``BuildContext`` to produce a built template under ``build_dir``.

    The caller is responsible for staging the case dir under a temp root
    (see :func:`_stage_case_dir`) and pointing ``staged_template_path`` at
    the staged copy. ``build_dir`` should sit inside the same staged tree
    so ``ApplicationBuilder.update_template`` produces the canonical
    ``.aws-sam/build/<full_path>`` relative paths.

    Returns the parsed dict read back from ``<build_dir>/template.yaml``.
    The on-disk file is left in place so callers (notably
    :func:`run_package_pipeline`) can hand the path to ``PackageContext``
    directly.
    """
    bctx = BuildContext(
        resource_identifier=None,
        template_file=str(staged_template_path),
        base_dir=str(staged_template_path.parent),
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

    return _read_template_as_plain_dict(build_dir / "template.yaml")


def run_build_pipeline(template_path: Path, language_extensions: bool) -> Dict[str, Any]:
    """In-process equivalent of ``sam build`` for a single template.

    Stages the case dir (``template.yaml`` + ``src/``) into a fresh temp
    tree, drives :class:`BuildContext` end-to-end, and returns the parsed
    built template dict. ``CodeUri`` etc. emerge as the canonical
    ``.aws-sam/build/<full_path>`` relative path that real ``sam build``
    writes — no post-processing needed.
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staged = _stage_case_dir(template_path.parent, tmp_path)
        build_dir = staged / ".aws-sam" / "build"
        cache_dir = staged / ".aws-sam" / "cache"
        return run_build_pipeline_to_dir(staged / template_path.name, language_extensions, build_dir, cache_dir)


def run_package_pipeline(template_path: Path, language_extensions: bool) -> Dict[str, Any]:
    """In-process equivalent of ``sam package``.

    Runs the build pipeline first (against a staged copy of the case dir)
    to produce a real on-disk ``.aws-sam/build/template.yaml``, then drives
    :class:`PackageContext` against that template. The S3 uploader is
    stubbed for determinism; everything else (LE expansion, ForEach merge,
    Mappings generation, AWS::Include export) runs through real code.
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        staged = _stage_case_dir(template_path.parent, tmp_path)
        build_dir = staged / ".aws-sam" / "build"
        cache_dir = staged / ".aws-sam" / "cache"

        # Re-run the build phase so we have a freshly built template on
        # disk that PackageContext can read. We can't reuse a previously
        # produced dict because PackageContext re-loads the template from
        # the path itself.
        run_build_pipeline_to_dir(staged / template_path.name, language_extensions, build_dir, cache_dir)

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
        staged = _stage_case_dir(template_path.parent, tmp_path)
        build_dir = staged / ".aws-sam" / "build"
        cache_dir = staged / ".aws-sam" / "cache"
        build_dict = run_build_pipeline_to_dir(staged / template_path.name, language_extensions, build_dir, cache_dir)

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
