"""Unit tests for run_build_pipeline.

The pipeline drives the real :class:`BuildContext`; these tests assert that
the in-process flow matches what real ``sam build`` writes to
``.aws-sam/build/template.yaml``:

- SAM templates: ``AWS::Serverless::Function`` is preserved, ``CodeUri``
  is rewritten to the build-artifact placeholder. The SAM transform runs
  server-side at deploy time, not at build time, so no auto-generated
  IAM Role appears in the build output.
- Raw CFN ``AWS::Lambda::Function``: ``Code`` is rewritten to the
  placeholder; the resource type is preserved.
- LE ``Fn::ForEach`` templates: the ForEach key is preserved at the top
  of ``Resources``; the body's artifact property is the placeholder.
"""

from pathlib import Path

from tests.golden.harness import run_build_pipeline

CASES_ROOT = Path(__file__).parent / "templates"


def test_build_sam_case_preserves_serverless_function():
    case = CASES_ROOT / "sam_resources" / "serverless_function_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=False)
    func = result["Resources"]["HelloFunction"]
    # SAM transform is server-side; build output keeps AWS::Serverless::Function.
    assert func["Type"] == "AWS::Serverless::Function"
    assert func["Properties"]["CodeUri"] == "<<BUILT_ARTIFACT>>"
    # No auto-generated IAM Role at build time.
    assert "HelloFunctionRole" not in result["Resources"]


def test_build_le_case_preserves_foreach():
    """LE templates must keep Fn::ForEach::* in the output.

    Real ``sam build`` produces a template that preserves the original
    ``Fn::ForEach`` structure so CloudFormation can re-expand it server-side
    at deploy time. Inside the body, the artifact property is rewritten to
    the build placeholder. The body resource type stays
    ``AWS::Serverless::Function`` because the SAM transform also runs
    server-side, not at build time. See PR #8637.
    """
    case = CASES_ROOT / "language_extensions" / "foreach_static_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=True)

    # ForEach key preserved at the top of Resources.
    foreach_keys = [k for k in result["Resources"] if k.startswith("Fn::ForEach")]
    assert foreach_keys, "Fn::ForEach::* must survive the build pipeline for LE templates"

    # The expanded resource ids must NOT appear at the top level — that would
    # mean the ForEach got expanded away, which is exactly the bug PR #8637
    # fixed. The harness must mirror real-world output.
    assert "AlphaFunction" not in result["Resources"]
    assert "BetaFunction" not in result["Resources"]

    # Body is still a Serverless::Function (SAM transform runs server-side),
    # and its CodeUri now points at the placeholder.
    foreach_value = result["Resources"][foreach_keys[0]]
    body = foreach_value[2]
    body_resource = next(iter(body.values()))
    assert body_resource["Type"] == "AWS::Serverless::Function"
    assert body_resource["Properties"]["CodeUri"] == "<<BUILT_ARTIFACT>>"


def test_build_cfn_case_replaces_code_with_placeholder():
    case = CASES_ROOT / "packageable_resources" / "lambda_function_zip"
    result = run_build_pipeline(case / "template.yaml", language_extensions=False)
    func = result["Resources"]["HelloFunction"]
    assert func["Type"] == "AWS::Lambda::Function"
    assert func["Properties"]["Code"] == "<<BUILT_ARTIFACT>>"
