[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/aws/aws-sam-cli)

# Contributing Guidelines

Thank you for your interest in contributing to our project. Whether it's a bug report, new feature, correction, or additional 
documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary 
information to effectively respond to your bug report or contribution.

## AI Usage

While using generative AI is allowed when contributing to this project, please keep the following points in mind:

* Review all code yourself before you submit it.
* Understand all the code you have submitted in order to answer any questions the maintainers could have when reviewing your PR.
* Avoid being overly verbose in code and testing - extra code can be hard to review.
  * For example, avoid writing unit tests that duplicate existing ones, or test libraries that you're using.
* Keep PR descriptions, comments, and follow ups concise.
* Ensure AI-generated code meets the same quality standards as human-written code.

## Development Guide

Refer to the [Development Guide](DEVELOPMENT_GUIDE.md) for help with environment setup, running tests, submitting a PR, or anything that will make you more productive.


## Reporting Bugs/Feature Requests

We welcome you to use the GitHub issue tracker to report bugs or suggest features.

When filing an issue, please check [existing open](https://github.com/aws/aws-sam-cli/issues), or [recently closed](https://github.com/aws/aws-sam-cli/issues?utf8=%E2%9C%93&q=is%3Aissue%20is%3Aclosed%20), issues to make sure somebody else hasn't already 
reported the issue. Please try to include as much information as you can. Details like these are incredibly useful:

* A reproducible test case or series of steps
* The version of our code being used
* Any modifications you've made relevant to the bug
* Anything unusual about your environment or deployment


## Contributing via Pull Requests
Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the *develop* branch.
2. You check existing open, and recently merged, pull requests to make sure someone else hasn't addressed the problem already.
3. You open an issue to discuss any significant work - we would hate for your time to be wasted.
4. The change works in Python3 (see supported Python Versions in setup.py)
5. Does the PR have updated/added unit, functional, and integration tests?
6. PR is merged submitted to merge into develop.

To send us a pull request, please:

1. Fork the repository.
2. Modify the source; please focus on the specific change you are contributing. If you also reformat all the code, it will be hard for us to focus on your change.
3. Ensure local tests pass.
4. Commit to your fork using clear commit messages.
5. Send us a pull request, answering any default questions in the pull request interface.
6. Pay attention to any automated CI failures reported in the pull request, and stay involved in the conversation.

GitHub provides additional document on [forking a repository](https://help.github.com/articles/fork-a-repo/) and 
[creating a pull request](https://help.github.com/articles/creating-a-pull-request/).


## Integration Test Guidelines

Integration tests run in CI via `.github/workflows/integration-tests.yml`. All jobs have AWS credentials. Tests in `build` and `local` jobs that require credentials are separated using a pytest marker.

### Tests that require AWS credentials

Some tests in `tests/integration/buildcmd/` and `tests/integration/local/` need AWS credentials (e.g. STS calls, Lambda layer publishing, SAR template resolution). These are:

- **Excluded** from build/local jobs via `-m "not requires_credential"`
- **Collected and run** in the dedicated `cloud-based-tests` CI job via `-m requires_credential`

To mark a test that requires AWS credentials, add the marker:

```python
import pytest

@pytest.mark.requires_credential
class TestMyCloudFeature(SomeBaseClass):
    ...
```

The marker is registered in `tests/conftest.py`. Build and local jobs automatically exclude these tests; `cloud-based-tests` automatically includes them.

### Docker container cleanup in parallel tests

`start-api` and `start-lambda` tests run in parallel (`-n 2`). Each test class snapshots existing Docker container IDs before starting its local server, and on teardown only removes containers created after the snapshot. This prevents one worker from killing another worker's containers.

If you write a new base class that manages Docker containers, follow the same pattern in `start_lambda_api_integ_base.py` and `start_api_integ_base.py`: snapshot container IDs in `setUpClass`, and scope removal to only new containers in `tearDownClass`.

### Tier 1 cross-platform smoke tests

A curated subset of ~50 tests marked with `@pytest.mark.tier1` runs on every OS/container-runtime combination (e.g. Linux+Finch). These validate platform-specific code paths: file system operations, container runtime interaction, process spawning, and network operations.

Run locally with: `pytest -m tier1 tests/integration tests/regression`

To add a tier 1 test for a new feature:

1. Add a dedicated `test_tier1_*` method that calls the existing test logic with one specific parameter set:

```python
@pytest.mark.tier1
def test_tier1_my_feature(self):
    """Single test for cross-platform validation."""
    self._test_my_feature("runtime_x", use_container=False)

@pytest.mark.tier1
@skipIf(SKIP_DOCKER_TESTS or SKIP_DOCKER_BUILD, SKIP_DOCKER_MESSAGE)
def test_tier1_my_feature_in_container(self):
    """Single container test for cross-platform validation."""
    self._test_my_feature("runtime_x", use_container=True)
```

2. Remove the matching parameter from the `@parameterized.expand` list to avoid running it twice in the Linux+Docker CI.

3. Each runtime should have one non-container and one container tier 1 test.

See `tests/integration/TIER1_TESTS.md` for the full list of selected tests.


## Finding contributions to work on
Looking at the existing issues is a great way to find something to contribute on. As our projects, by default, use the default GitHub issue labels ((enhancement/bug/duplicate/help wanted/invalid/question/wontfix), looking at any ['help wanted'](https://github.com/aws/aws-sam-cli/labels/help%20wanted) issues is a great place to start. 

## First time contributors
If this your first time looking to contribute, looking at any ['contributors/welcome'](https://github.com/aws/aws-sam-cli/labels/contributors%2Fwelcome) or ['contributors/good-first-issue'](https://github.com/aws/aws-sam-cli/labels/contributors%2Fgood-first-issue) issues is a great place to start. 


## Code of Conduct
This project has adopted the [Amazon Open Source Code of Conduct](https://aws.github.io/code-of-conduct). 
For more information see the [Code of Conduct FAQ](https://aws.github.io/code-of-conduct-faq) or contact 
opensource-codeofconduct@amazon.com with any additional questions or comments.


## Security issue notifications
If you discover a potential security issue in this project we ask that you notify AWS/Amazon Security via our [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public github issue.


## Licensing

See the [LICENSE](https://github.com/aws/aws-sam-cli/blob/master/LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.

We may ask you to sign a [Contributor License Agreement (CLA)](http://en.wikipedia.org/wiki/Contributor_License_Agreement) for larger changes.
