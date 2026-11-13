"""Unit tests for run_package_pipeline.

The pipeline drives the real :class:`PackageContext` (after a real build
phase); these tests assert that the on-disk packaged template matches
what real ``sam package`` writes:

- SAM templates: ``AWS::Serverless::Function`` is preserved (no SAM
  transform); ``CodeUri`` becomes an ``s3://golden-bucket/<sha>`` URI.
- Raw CFN ``AWS::Lambda::Function``: ``Code`` becomes
  ``{S3Bucket: golden-bucket, S3Key: <sha>}``.
- LE templates: ``Fn::ForEach::*`` is preserved; the body's artifact
  property is rewritten to a single ``s3://`` URI.
"""

from pathlib import Path

from tests.golden.harness import run_package_pipeline

CASES_ROOT = Path(__file__).parent / "templates"


def test_package_sam_case_rewrites_codeuri_to_s3():
    case = CASES_ROOT / "sam_resources" / "serverless_function_zip"
    pkg_out = run_package_pipeline(case / "template.yaml", language_extensions=False)
    func = pkg_out["Resources"]["HelloFunction"]
    assert func["Type"] == "AWS::Serverless::Function"
    code_uri = func["Properties"]["CodeUri"]
    assert isinstance(code_uri, str)
    assert code_uri.startswith("s3://golden-bucket/")


def test_package_le_case_preserves_foreach_with_s3_uri():
    """LE templates must keep Fn::ForEach::* through the package pipeline.

    The body's artifact property (CodeUri here) should be rewritten to an
    S3 URI string so that, at deploy time, CloudFormation can re-expand the
    ForEach and each iteration receives the same packaged artifact. See
    ``merge_language_extensions_s3_uris``.
    """
    case = CASES_ROOT / "language_extensions" / "foreach_static_zip"
    pkg_out = run_package_pipeline(case / "template.yaml", language_extensions=True)

    foreach_keys = [k for k in pkg_out["Resources"] if k.startswith("Fn::ForEach")]
    assert foreach_keys, "Fn::ForEach::* must survive the package pipeline for LE templates"
    # No expanded ids at the top level.
    assert "AlphaFunction" not in pkg_out["Resources"]
    assert "BetaFunction" not in pkg_out["Resources"]

    foreach_value = pkg_out["Resources"][foreach_keys[0]]
    body = foreach_value[2]
    body_resource = next(iter(body.values()))
    code_uri = body_resource["Properties"]["CodeUri"]
    # Single shared S3 URI for the whole loop (static collection, no
    # per-iteration Mappings needed).
    assert isinstance(code_uri, str)
    assert code_uri.startswith("s3://golden-bucket/")


def test_package_cfn_case_rewrites_raw_code_to_s3_dict():
    case = CASES_ROOT / "packageable_resources" / "lambda_function_zip"
    pkg_out = run_package_pipeline(case / "template.yaml", language_extensions=False)
    code = pkg_out["Resources"]["HelloFunction"]["Properties"]["Code"]
    # Raw Lambda::Function packaging emits {S3Bucket, S3Key}.
    assert isinstance(code, dict)
    assert code.get("S3Bucket") == "golden-bucket"
    assert "S3Key" in code


def test_package_is_deterministic():
    """Same input produces same output across runs."""
    case = CASES_ROOT / "sam_resources" / "serverless_function_zip"
    a = run_package_pipeline(case / "template.yaml", language_extensions=False)
    b = run_package_pipeline(case / "template.yaml", language_extensions=False)
    assert a == b
