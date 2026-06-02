"""Unit tests for run_package_pipeline."""

from pathlib import Path

from tests.golden.harness import run_build_pipeline, run_package_pipeline

CASES_ROOT = Path(__file__).parent / "templates"


def test_package_sam_case_rewrites_code_to_s3_uri():
    case = CASES_ROOT / "sam_resources" / "serverless_function_zip"
    build_out = run_build_pipeline(case / "template.yaml", language_extensions=False)
    pkg_out = run_package_pipeline(case / "template.yaml", build_out)
    code = pkg_out["Resources"]["HelloFunction"]["Properties"]["Code"]
    assert isinstance(code, dict)  # CFN Lambda Code becomes S3Bucket/S3Key dict
    assert code["S3Bucket"] == "golden-bucket"
    assert "S3Key" in code


def test_package_le_case_rewrites_each_expanded_codeuri():
    case = CASES_ROOT / "language_extensions" / "foreach_static_zip"
    build_out = run_build_pipeline(case / "template.yaml", language_extensions=True)
    pkg_out = run_package_pipeline(case / "template.yaml", build_out)
    for fn_id in ("AlphaFunction", "BetaFunction"):
        code = pkg_out["Resources"][fn_id]["Properties"]["Code"]
        assert isinstance(code, dict)
        assert code.get("S3Bucket") == "golden-bucket"


def test_package_cfn_case_rewrites_raw_code_path():
    case = CASES_ROOT / "packageable_resources" / "lambda_function_zip"
    build_out = run_build_pipeline(case / "template.yaml", language_extensions=False)
    pkg_out = run_package_pipeline(case / "template.yaml", build_out)
    code = pkg_out["Resources"]["HelloFunction"]["Properties"]["Code"]
    assert isinstance(code, dict)
    assert code.get("S3Bucket") == "golden-bucket"


def test_package_is_deterministic():
    """Same input produces same output across runs."""
    case = CASES_ROOT / "sam_resources" / "serverless_function_zip"
    build_out = run_build_pipeline(case / "template.yaml", language_extensions=False)
    a = run_package_pipeline(case / "template.yaml", build_out)
    b = run_package_pipeline(case / "template.yaml", build_out)
    assert a == b
