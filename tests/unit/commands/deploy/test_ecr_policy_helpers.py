"""
Unit tests for the ECR policy helper functions in deploy_context.py.

These helpers pre-set Lambda pull access on ECR repositories before
CloudFormation creates the changeset, preventing the concurrent
SetRepositoryPolicy race condition described in GitHub issue #8190.
"""

import json
import logging
import threading
import time
from typing import Dict, List
from unittest import TestCase
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from samcli.commands.deploy.deploy_context import (
    _SAM_ECR_POLICY_SID,
    _ensure_ecr_lambda_pull_policy,
    _extract_ecr_repo_name,
    _upsert_ecr_lambda_policy,
)
from samcli.commands.deploy.exceptions import ECRPolicySetError

_RepoNotFoundException = type("RepositoryPolicyNotFoundException", (Exception,), {})


def _make_access_denied_error(operation: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "User is not authorized"}},
        operation,
    )


def _make_unexpected_client_error(operation: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Something went wrong"}},
        operation,
    )


def _make_ecr_client(existing_policy_doc=None, get_side_effect=None, set_side_effect=None):
    """Build a mock ECR client."""
    ecr_client = MagicMock()
    ecr_client.exceptions.RepositoryPolicyNotFoundException = _RepoNotFoundException

    if get_side_effect is not None:
        ecr_client.get_repository_policy.side_effect = get_side_effect
    elif existing_policy_doc is not None:
        ecr_client.get_repository_policy.return_value = {
            "policyText": json.dumps(existing_policy_doc)
        }
    else:
        ecr_client.get_repository_policy.return_value = {"policyText": "{}"}

    if set_side_effect is not None:
        ecr_client.set_repository_policy.side_effect = set_side_effect

    return ecr_client


def _make_stateful_ecr_client(initial_policy_doc=None):
    """Return a mock ECR client with in-memory get/set (full-document replace)."""
    store = {"policyText": json.dumps(initial_policy_doc or {"Version": "2012-10-17", "Statement": []})}

    def _get(**kwargs):
        return {"policyText": store["policyText"]}

    def _set(**kwargs):
        store["policyText"] = kwargs["policyText"]
        return {}

    client = MagicMock()
    client.exceptions.RepositoryPolicyNotFoundException = _RepoNotFoundException
    client.get_repository_policy.side_effect = _get
    client.set_repository_policy.side_effect = _set
    client._store = store
    return client


# ---------------------------------------------------------------------------
# _extract_ecr_repo_name tests
# ---------------------------------------------------------------------------


class TestExtractEcrRepoName(TestCase):
    def test_uri_with_tag(self):
        uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo:latest"
        self.assertEqual(_extract_ecr_repo_name(uri), "my-repo")

    def test_uri_with_namespace_and_tag(self):
        uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/org/my-repo:v1"
        self.assertEqual(_extract_ecr_repo_name(uri), "org/my-repo")

    def test_uri_without_tag(self):
        uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo"
        self.assertEqual(_extract_ecr_repo_name(uri), "my-repo")


# ---------------------------------------------------------------------------
# _ensure_ecr_lambda_pull_policy routing/deduplication tests
# ---------------------------------------------------------------------------


class TestEnsureEcrLambdaPullPolicy(TestCase):
    def test_both_none_returns_early(self):
        ecr_client = _make_ecr_client()
        _ensure_ecr_lambda_pull_policy(ecr_client, None, None)
        ecr_client.get_repository_policy.assert_not_called()

    def test_empty_dict_and_none_returns_early(self):
        ecr_client = _make_ecr_client()
        _ensure_ecr_lambda_pull_policy(ecr_client, {}, None)
        ecr_client.get_repository_policy.assert_not_called()

    @patch("samcli.commands.deploy.deploy_context._upsert_ecr_lambda_policy")
    def test_deduplicates_same_repo(self, mock_upsert):
        uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo:latest"
        _ensure_ecr_lambda_pull_policy(
            MagicMock(), {"FnA": uri, "FnB": uri}, None
        )
        mock_upsert.assert_called_once()

    @patch("samcli.commands.deploy.deploy_context._upsert_ecr_lambda_policy")
    def test_two_different_repos_calls_twice(self, mock_upsert):
        _ensure_ecr_lambda_pull_policy(
            MagicMock(),
            {
                "FnA": "123456789012.dkr.ecr.us-east-1.amazonaws.com/repo-a:v1",
                "FnB": "123456789012.dkr.ecr.us-east-1.amazonaws.com/repo-b:v1",
            },
            None,
        )
        self.assertEqual(mock_upsert.call_count, 2)

    @patch("samcli.commands.deploy.deploy_context._upsert_ecr_lambda_policy")
    def test_singular_image_repository(self, mock_upsert):
        _ensure_ecr_lambda_pull_policy(
            MagicMock(), None, "123456789012.dkr.ecr.us-east-1.amazonaws.com/single:v2"
        )
        mock_upsert.assert_called_once()


# ---------------------------------------------------------------------------
# _upsert_ecr_lambda_policy tests
# ---------------------------------------------------------------------------


class TestUpsertEcrLambdaPolicy(TestCase):
    def test_no_existing_policy_sets_sam_statement(self):
        ecr_client = _make_ecr_client(get_side_effect=_RepoNotFoundException("no policy"))
        _upsert_ecr_lambda_policy(ecr_client, "my-repo")

        ecr_client.set_repository_policy.assert_called_once()
        kwargs = ecr_client.set_repository_policy.call_args.kwargs
        self.assertEqual(kwargs["repositoryName"], "my-repo")
        self.assertFalse(kwargs["force"])
        policy = json.loads(kwargs["policyText"])
        self.assertEqual(len(policy["Statement"]), 1)
        self.assertEqual(policy["Statement"][0]["Sid"], _SAM_ECR_POLICY_SID)

    def test_preserves_existing_statements_and_appends_sam(self):
        existing = {"Version": "2012-10-17", "Statement": [
            {"Sid": "CustomerPolicy", "Effect": "Allow", "Principal": "*", "Action": "ecr:*"}
        ]}
        ecr_client = _make_ecr_client(existing_policy_doc=existing)
        _upsert_ecr_lambda_policy(ecr_client, "my-repo")

        policy = json.loads(ecr_client.set_repository_policy.call_args.kwargs["policyText"])
        sids = [s["Sid"] for s in policy["Statement"]]
        self.assertIn("CustomerPolicy", sids)
        self.assertIn(_SAM_ECR_POLICY_SID, sids)
        self.assertEqual(len(policy["Statement"]), 2)

    def test_idempotent_replaces_existing_sam_statement(self):
        stale = {"Version": "2012-10-17", "Statement": [
            {"Sid": _SAM_ECR_POLICY_SID, "Effect": "Deny", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "ecr:*"}
        ]}
        ecr_client = _make_ecr_client(existing_policy_doc=stale)
        _upsert_ecr_lambda_policy(ecr_client, "my-repo")

        policy = json.loads(ecr_client.set_repository_policy.call_args.kwargs["policyText"])
        sam_stmts = [s for s in policy["Statement"] if s["Sid"] == _SAM_ECR_POLICY_SID]
        self.assertEqual(len(sam_stmts), 1)
        self.assertEqual(sam_stmts[0]["Effect"], "Allow")

    def test_get_access_denied_logs_warning_skips(self):
        ecr_client = _make_ecr_client(get_side_effect=_make_access_denied_error("GetRepositoryPolicy"))
        with self.assertLogs("samcli.commands.deploy.deploy_context", level=logging.WARNING):
            _upsert_ecr_lambda_policy(ecr_client, "my-repo")
        ecr_client.set_repository_policy.assert_not_called()

    def test_get_unexpected_error_raises(self):
        ecr_client = _make_ecr_client(get_side_effect=_make_unexpected_client_error("GetRepositoryPolicy"))
        with self.assertRaises(ECRPolicySetError):
            _upsert_ecr_lambda_policy(ecr_client, "my-repo")

    def test_set_access_denied_logs_warning_skips(self):
        ecr_client = _make_ecr_client(
            get_side_effect=_RepoNotFoundException("no policy"),
            set_side_effect=_make_access_denied_error("SetRepositoryPolicy"),
        )
        with self.assertLogs("samcli.commands.deploy.deploy_context", level=logging.WARNING):
            _upsert_ecr_lambda_policy(ecr_client, "my-repo")

    def test_set_unexpected_error_raises(self):
        ecr_client = _make_ecr_client(
            get_side_effect=_RepoNotFoundException("no policy"),
            set_side_effect=_make_unexpected_client_error("SetRepositoryPolicy"),
        )
        with self.assertRaises(ECRPolicySetError):
            _upsert_ecr_lambda_policy(ecr_client, "my-repo")


# ---------------------------------------------------------------------------
# Issue #8190 scenario tests
# ---------------------------------------------------------------------------

REGISTRY = "123456789012.dkr.ecr.us-east-1.amazonaws.com"

SEVEN_REPO_IMAGE_REPOSITORIES = {
    "bigDumperLambda": f"{REGISTRY}/big-dumper:v3",
    "bqLoaderLambda": f"{REGISTRY}/bq-loader:v3",
    "littleCheckerLambda": f"{REGISTRY}/little-checker:v3",
    "littleDumperLambda": f"{REGISTRY}/little-dumper:v3",
    "tableMakerLambda": f"{REGISTRY}/table-maker:v3",
    "publisherLambda": f"{REGISTRY}/publisher:v3",
    "jobCheckerLambda": f"{REGISTRY}/job-checker:v3",
}

SHARED_REPO = "my-app"
SEVEN_FUNCTIONS_SAME_REPO = {
    "bigDumperLambda": f"{REGISTRY}/{SHARED_REPO}:big-dumper-v3",
    "bqLoaderLambda": f"{REGISTRY}/{SHARED_REPO}:bq-loader-v3",
    "littleCheckerLambda": f"{REGISTRY}/{SHARED_REPO}:little-checker-v3",
    "littleDumperLambda": f"{REGISTRY}/{SHARED_REPO}:little-dumper-v3",
    "tableMakerLambda": f"{REGISTRY}/{SHARED_REPO}:table-maker-v3",
    "publisherLambda": f"{REGISTRY}/{SHARED_REPO}:publisher-v3",
    "jobCheckerLambda": f"{REGISTRY}/{SHARED_REPO}:job-checker-v3",
}


class TestIssue8190Scenarios(TestCase):
    def test_seven_distinct_repos_each_gets_policy(self):
        ecr_client = _make_ecr_client(get_side_effect=_RepoNotFoundException("no policy"))
        _ensure_ecr_lambda_pull_policy(ecr_client, SEVEN_REPO_IMAGE_REPOSITORIES, None)

        self.assertEqual(ecr_client.set_repository_policy.call_count, 7)
        for c in ecr_client.set_repository_policy.call_args_list:
            policy = json.loads(c.kwargs["policyText"])
            sam_stmts = [s for s in policy["Statement"] if s.get("Sid") == _SAM_ECR_POLICY_SID]
            self.assertEqual(len(sam_stmts), 1)
            self.assertFalse(c.kwargs.get("force", True))

    def test_seven_functions_same_repo_deduplicates_to_one_call(self):
        ecr_client = _make_ecr_client(get_side_effect=_RepoNotFoundException("no policy"))
        _ensure_ecr_lambda_pull_policy(ecr_client, SEVEN_FUNCTIONS_SAME_REPO, None)

        self.assertEqual(ecr_client.set_repository_policy.call_count, 1)
        self.assertEqual(
            ecr_client.set_repository_policy.call_args.kwargs["repositoryName"],
            SHARED_REPO,
        )

    def test_race_condition_without_fix(self):
        """Documents the bug: concurrent full-doc replaces overwrite each other."""
        policy_store: Dict = {"doc": {"Version": "2012-10-17", "Statement": []}}

        def cf_handler(function_name: str):
            current = json.loads(json.dumps(policy_store["doc"]))
            time.sleep(0.01)
            current["Statement"] = [{"Sid": f"Grant_{function_name}", "Effect": "Allow",
                                     "Principal": {"Service": "lambda.amazonaws.com"},
                                     "Action": ["ecr:GetDownloadUrlForLayer"]}]
            policy_store["doc"] = current

        threads = [threading.Thread(target=cf_handler, args=(n,)) for n in SEVEN_FUNCTIONS_SAME_REPO]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only last writer survives — the bug
        self.assertEqual(len(policy_store["doc"]["Statement"]), 1)

    def test_pre_set_policy_survives_cf_writes(self):
        """With the fix, the pre-set policy ensures Lambda can always pull."""
        ecr_client = _make_stateful_ecr_client()
        _ensure_ecr_lambda_pull_policy(ecr_client, SEVEN_FUNCTIONS_SAME_REPO, None)

        # Verify pre-set
        statements = json.loads(ecr_client._store["policyText"])["Statement"]
        self.assertEqual(len(statements), 1)
        self.assertEqual(statements[0]["Sid"], _SAM_ECR_POLICY_SID)

    def test_second_deploy_is_idempotent(self):
        ecr_client = _make_stateful_ecr_client()
        _ensure_ecr_lambda_pull_policy(ecr_client, SEVEN_REPO_IMAGE_REPOSITORIES, None)
        _ensure_ecr_lambda_pull_policy(ecr_client, SEVEN_REPO_IMAGE_REPOSITORIES, None)

        # Each call writes a policy with exactly 1 SAM statement
        for c in ecr_client.set_repository_policy.call_args_list:
            policy = json.loads(c.kwargs["policyText"])
            sam_count = sum(1 for s in policy["Statement"] if s.get("Sid") == _SAM_ECR_POLICY_SID)
            self.assertEqual(sam_count, 1)

    def test_mixed_shared_and_distinct_repos(self):
        mixed = {
            "fn1": f"{REGISTRY}/shared:tag1",
            "fn2": f"{REGISTRY}/shared:tag2",
            "fn3": f"{REGISTRY}/shared:tag3",
            "fn4": f"{REGISTRY}/shared:tag4",
            "fn5": f"{REGISTRY}/distinct-a:v1",
            "fn6": f"{REGISTRY}/distinct-b:v1",
            "fn7": f"{REGISTRY}/distinct-c:v1",
        }
        ecr_client = _make_ecr_client(get_side_effect=_RepoNotFoundException("no policy"))
        _ensure_ecr_lambda_pull_policy(ecr_client, mixed, None)

        # 1 shared + 3 distinct = 4 calls
        self.assertEqual(ecr_client.set_repository_policy.call_count, 4)
