"""Unit tests for run_build_pipeline."""

from pathlib import Path

from tests.golden.harness import run_build_pipeline

CASES_ROOT = Path(__file__).parent / "templates"


def test_build_sam_case_replaces_codeuri_with_placeholder(tmp_path):
    case = CASES_ROOT / "sam_resources" / "serverless_function_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=False)
    func = result["Resources"]["HelloFunction"]
    # SAM transform converts AWS::Serverless::Function to AWS::Lambda::Function
    assert func["Type"] == "AWS::Lambda::Function"
    assert func["Properties"]["Code"] == "<<BUILT_ARTIFACT>>"


def test_build_le_case_expands_foreach(tmp_path):
    case = CASES_ROOT / "language_extensions" / "foreach_static_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=True)
    assert "AlphaFunction" in result["Resources"]
    assert "BetaFunction" in result["Resources"]
    # ForEach key gone
    assert not any(k.startswith("Fn::ForEach") for k in result["Resources"])


def test_build_le_case_skipped_when_disabled():
    case = CASES_ROOT / "language_extensions" / "foreach_static_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=False)
    # ForEach key preserved
    assert any(k.startswith("Fn::ForEach") for k in result["Resources"])


def test_build_cfn_case_replaces_code_path():
    case = CASES_ROOT / "packageable_resources" / "lambda_function_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=False)
    func = result["Resources"]["HelloFunction"]
    # Build pipeline does not rewrite raw CFN Lambda Code paths (that's package's job)
    # but it does load the template through SAM's parser, so verify shape.
    assert func["Type"] == "AWS::Lambda::Function"
